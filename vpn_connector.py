# -*- coding: utf-8 -*-
import logging
import paramiko # Для Outline
import sys 
import os
import requests
import json
import datetime
import math
import base64
import asyncio

import secrets # Импорт локального secrets.py для конфигураций
from typing import Tuple, Union
import uuid
import time


logger = logging.getLogger(__name__)

# --- Глобальные переменные для хранения сессии 3x-ui API ---
_xui_session_cookie = None
_xui_cookie_expiry = 0 # Метка времени истечения куки (или 0, если не задана)

def _find_server_config(server_id: int) -> dict | None:
    for server in secrets.SERVERS: 
        if server.get("id") == server_id:
            return server
    return None

async def execute_ssh_command(server_config: dict, command: str) -> Tuple[int, str, str]:
    client = None
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy()) 

        hostname = server_config.get('ip')
        port = server_config.get('vless_ssh_port', 22)
        username = server_config.get('vless_ssh_user', 'root')
        password = server_config.get('vless_ssh_password')
        pkey_path = server_config.get("vless_ssh_pkey_path")

        if not hostname or not username:
            logger.error(f"SSH configuration missing hostname or username for server {server_config.get('id', 'Unknown')}")
            return 1, "", "SSH configuration missing hostname or username"

        logger.debug(f"Connecting to SSH: {hostname}:{port} as {username}")

        if pkey_path:
            client.connect(hostname=hostname, port=port, username=username, key_filename=pkey_path, timeout=10)
        elif password:
            client.connect(hostname=hostname, port=port, username=username, password=password, timeout=10)
        else:
            logger.error(f"SSH credentials (password or key path) not provided for server {server_config.get('id', 'Unknown')}")
            return 1, "", "SSH credentials not provided"

        logger.info(f"Executing SSH command: {command}")
        stdin, stdout, stderr = client.exec_command(command, timeout=20)

        stdout_output = stdout.read().decode('utf-8', errors='ignore').strip()
        stderr_output = stderr.read().decode('utf-8', errors='ignore').strip()
        exit_code = stdout.channel.recv_exit_status()

        logger.debug(f"Command finished. Exit code: {exit_code}")
        if stdout_output: logger.debug(f"STDOUT:\n{stdout_output}")
        if stderr_output: logger.debug(f"STDERR:\n{stderr_output}")

        return exit_code, stdout_output, stderr_output

    except paramiko.AuthenticationException:
        logger.error("SSH Authentication failed. Check username, password, or key.")
        return 1, "", "SSH Authentication failed"
    except paramiko.SSHException as e:
        logger.error(f"SSH error during command execution: {e}")
        return 1, "", f"SSH error: {e}"
    except Exception as e:
        logger.error(f"An unexpected error occurred during SSH execution: {e}", exc_info=True)
        return 1, "", f"An unexpected error occurred during SSH execution: {e}"
    finally:
        if client:
            client.close()


async def _get_xui_session() -> Union[str, None]:
    global _xui_session_cookie, _xui_cookie_expiry

    if _xui_session_cookie and _xui_cookie_expiry > time.time() + 60:
        logger.debug("Using existing 3x-ui session cookie.")
        return _xui_session_cookie

    if not secrets.XUI_API_URL or not secrets.XUI_USERNAME or not secrets.XUI_PASSWORD:
        logger.error("3x-ui API credentials are not fully configured in secrets.py. XUI_API_URL, XUI_USERNAME, or XUI_PASSWORD is missing or default.")
        return None

    login_url = f"{secrets.XUI_API_URL}/login"
    
    login_data = {
        "username": secrets.XUI_USERNAME,
        "password": secrets.XUI_PASSWORD
    }
    
    headers = {'Content-Type': 'application/json'}

    logger.info(f"Attempting to log in to 3x-ui panel via POST at {login_url} with username: {secrets.XUI_USERNAME} (password hidden)...") 

    try:
        response = requests.post(login_url, headers=headers, json=login_data, verify=False, timeout=15)
        response.raise_for_status() 
        response_json = {} 
        try:
            response_json = response.json()
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from 3x-ui login response. Status: {response.status_code}. Raw response body: {response.text[:500]}...")
            return None
        
        if response_json.get("success"):
            session_cookie_data = response.cookies.get('session') or response.cookies.get('3x-ui')

            if session_cookie_data is not None:
                cookie_name = '3x-ui' if '3x-ui' in response.cookies else 'session'
                _xui_session_cookie = f"{cookie_name}={session_cookie_data}"
                _xui_cookie_expiry = time.time() + 3600 
                
                try:
                    for cookie in response.cookies:
                        if cookie.name == cookie_name:
                            _xui_cookie_expiry = cookie.expires or (time.time() + 3600)
                            break
                except Exception as ex:
                    logger.warning(f"Could not get cookie expiry time from requests.response.cookies: {ex}")


                logger.info(f"Successfully logged in to 3x-ui. Session cookie: {_xui_session_cookie[:20]}..., Expires: {datetime.datetime.fromtimestamp(_xui_cookie_expiry).strftime('%Y-%m-%d %H:%M:%S')}")
                return _xui_session_cookie
            else:
                logger.error(f"Session cookie not found in successful login JSON response. Status: {response.status_code}, Success: {response_json.get('success')}. Full response: {response.text}")
                return None
        else:
            logger.error(f"3x-ui login failed. Response success is false. Message: {response_json.get('msg', 'No message')}. Full response: {response.text}")
            return None

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error during 3x-ui login to {login_url}: {e.response.status_code} - {e.response.text}")
        if e.response.status_code == 401:
            logger.warning("3x-ui API returned 401 Unauthorized. Clearing session cookie.")
            _xui_session_cookie = None
            _xui_cookie_expiry = 0
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error during 3x-ui login to {login_url}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during 3x-ui login to {login_url}: {e}", exc_info=True)
        return None

async def _xui_api_request(method: str, path: str, json_data: dict | None = None) -> dict | None:
    session_cookie = await _get_xui_session()
    if not session_cookie:
        logger.error("Failed to get 3x-ui session cookie for API request. Aborting.")
        return None
    url = f"{secrets.XUI_API_URL}{path}"
    headers = {
        'Content-Type': 'application/json',
        'Cookie': session_cookie 
    }

    try:
        response = requests.request(method, url, headers=headers, json=json_data, verify=False, timeout=20)
        response.raise_for_status()

        return response.json()

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error during 3x-ui API request {method} {path}: {e.response.status_code} - {e.response.text}")
        if e.response.status_code == 401:
            logger.warning("3x-ui API returned 401 Unauthorized. Clearing session cookie.")
            global _xui_session_cookie, _xui_cookie_expiry
            _xui_session_cookie = None
            _xui_cookie_expiry = 0
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error during 3x-ui API request {method} {path}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during 3x-ui API request {method} {path}: {e}", exc_info=True)
        return None

async def _xui_get_inbound_clients(inbound_id: int) -> list[dict] | None:

    get_inbound_path = f"/panel/api/inbounds/get/{inbound_id}"
    max_retries = 5 
    retry_delay_sec = 2 

    for attempt in range(max_retries):
        inbound_data = await _xui_api_request("GET", get_inbound_path)

        if inbound_data and inbound_data.get("success") and inbound_data.get("obj"):
            inbound_obj = inbound_data.get("obj")
            try:
                settings = json.loads(inbound_obj.get("settings", "{}"))
                clients = settings.get("clients", [])
                return clients
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON settings for inbound {inbound_id} (Attempt {attempt + 1}/{max_retries}).")
                return [] 
            except Exception as e:
                logger.error(f"An unexpected error occurred while getting clients for inbound {inbound_id} (Attempt {attempt + 1}/{max_retries}): {e}", exc_info=True)
                return [] 
        else:
            error_msg = inbound_data.get("msg", "") if inbound_data else "Unknown error"
            logger.warning(f"Failed to fetch inbound config {inbound_id} (Attempt {attempt + 1}/{max_retries}). Response: {inbound_data}. Message: {error_msg}")
            
            if "database is locked" in error_msg.lower() and attempt < max_retries - 1:
                logger.info(f"Database locked, retrying in {retry_delay_sec} seconds...")
                await asyncio.sleep(retry_delay_sec) 
            else:
                logger.info(f"Failed to get existing clients for inbound {inbound_id} after {attempt + 1} attempts. Returning empty list to proceed with new key creation.")
                return []
    logger.error(f"All {max_retries} attempts failed to fetch inbound clients for inbound {inbound_id}. Returning empty list.")
    return [] 


async def _xui_add_vless_client(server_config: dict, user_telegram_id: int, user_username: str | None, total_traffic_gb: Union[int, None] = None) -> Tuple[Union[str, None], Union[str, None]]:
    inbound_id = server_config.get("xui_vless_inbound_id")
    if inbound_id is None:
        logger.error(f"3x-ui VLESS inbound ID not configured for server {server_config.get('id', 'Unknown')}.")
        return None, None

    base_email_name = f"tg_{user_telegram_id}"
    if user_username:
        cleaned_username = ''.join(c if c.isalnum() else '_' for c in user_username).lower()
        base_email_name += f"_{cleaned_username}"
    
    random_suffix_bytes = os.urandom(10)
    random_suffix = base64.urlsafe_b64encode(random_suffix_bytes).decode('utf-8').rstrip('=') 

    user_email = f"{base_email_name}_{random_suffix}@bot.local"
        
    client_uuid = str(uuid.uuid4()) 

    total_traffic_bytes = (total_traffic_gb * 1024 * 1024 * 1024) if total_traffic_gb is not None and total_traffic_gb > 0 else 0

    new_client_data = {
        "id": client_uuid,
        "email": user_email,
        "enable": True,
        "totalGB": total_traffic_bytes,
        "expiryTime": 0,
        "limitIp": 0,
        "flow": server_config.get("xui_vless_flow", ""),
        "tgId": str(user_telegram_id), 
        "subId": "", 
        "comment": "", 
        "reset": 0
    }

    add_client_payload = {
        "id": inbound_id,
        "settings": json.dumps({"clients": [new_client_data]}) 
    }

    add_client_path = "/panel/inbound/addClient" 
    
    logger.info(f"Attempting to add VLESS client via 3x-ui API ({add_client_path}) for inbound {inbound_id}, email: {user_email}")
    logger.debug(f"Payload for addClient: {add_client_payload}")

    add_response_data = await _xui_api_request("POST", add_client_path, json_data=add_client_payload)

    if add_response_data and add_response_data.get("success"):
        logger.info(f"VLESS client added successfully via 3x-ui API. Email: {user_email}, UUID: {client_uuid}")

        inbound_data_fresh = await _xui_api_request("GET", f"/panel/api/inbounds/get/{inbound_id}")

        if not (inbound_data_fresh and inbound_data_fresh.get("success") and inbound_data_fresh.get("obj")):
            logger.error(f"Failed to fetch inbound config {inbound_id} after adding client for link construction. Response: {inbound_data_fresh}")
            return None, user_email

        inbound_obj = inbound_data_fresh.get("obj")
        
        server_address = server_config.get('ip')
        if not server_address:
            logger.error(f"Server IP not found in secrets.SERVERS config for ID {server_config.get('id', 'Unknown')}!")
            server_address = inbound_obj.get("host") 
            if not server_address:
                logger.error(f"Could not find server address from inbound object or secrets.SERVERS for ID {server_config.get('id', 'Unknown')}.")
                return None, user_email

        inbound_port = inbound_obj.get("port")
        if not inbound_port:
            logger.error(f"Could not find inbound port for ID {inbound_id} in API response.")
            return None, user_email

        public_key = server_config.get("xui_vless_public_key")
        sni = server_config.get("xui_vless_sni")
        short_id = server_config.get("xui_vless_short_id")
        vless_flow = server_config.get("xui_vless_flow")

        if not all([public_key, sni, short_id]):
            logger.error(f"Missing Reality parameters (public_key, sni, or short_id) in secrets.py for server {server_config.get('id', 'Unknown')}. Cannot construct Reality link.")
            return None, user_email

        params = {
            "security": "reality",
            "sni": sni,
            "pbk": public_key,
            "sid": short_id,
        }
        if vless_flow:
            params["flow"] = vless_flow

        query_string_params = "&".join([f"{k}={v}" for k, v in params.items() if v is not None and v != ""])

        tag = user_email

        vless_link = f"vless://{client_uuid}@{server_address}:{inbound_port}"
        if query_string_params:
            vless_link += f"?{query_string_params}"
        vless_link += f"#{tag}"

        logger.info(f"Constructed VLESS Reality link for client {user_email}: {vless_link[:100]}...")
        return vless_link, user_email

    else:
        logger.error(f"Failed to add VLESS client via new 3x-ui API. Response: {add_response_data}. Full response: {json.dumps(add_response_data) if add_response_data else 'None'}")
        return None, user_email


async def _xui_add_shadowsocks_client(server_config: dict, user_telegram_id: int, user_username: str | None, total_traffic_gb: Union[int, None] = None) -> Tuple[Union[str, None], Union[str, None]]:

    inbound_id = server_config.get("xui_shadowsocks_inbound_id")
    if inbound_id is None:
        logger.error(f"3x-ui Shadowsocks inbound ID not configured for server {server_config.get('id', 'Unknown')}.")
        return None, None

    base_email_name = f"tg_{user_telegram_id}"
    if user_username:
        cleaned_username = ''.join(c if c.isalnum() else '_' for c in user_username).lower()
        base_email_name += f"_{cleaned_username}"

    random_suffix_bytes = os.urandom(10)
    random_suffix = base64.urlsafe_b64encode(random_suffix_bytes).decode('utf-8').rstrip('=') 

    user_email = f"{base_email_name}_{random_suffix}@bot.local"

    client_uuid = str(uuid.uuid4()) 

    total_traffic_bytes = (total_traffic_gb * 1024 * 1024 * 1024) if total_traffic_gb is not None and total_traffic_gb > 0 else 0
    
    ss_password_bytes = os.urandom(16)
    ss_password = base64.urlsafe_b64encode(ss_password_bytes).decode('utf-8').rstrip('=') 

    ss_method = server_config.get("xui_shadowsocks_method")
    if not ss_method:
        logger.error(f"Shadowsocks method not configured in secrets.py for server {server_config.get('id', 'Unknown')}.")
        return None, None

    new_client_data = {
        "id": client_uuid, 
        "email": user_email,
        "enable": True,
        "totalGB": total_traffic_bytes,
        "expiryTime": 0,
        "limitIp": 0,
        "method": ss_method, 
        "password": ss_password, 
        "tgId": str(user_telegram_id),
        "subId": "",
        "comment": "",
        "reset": 0
    }
    
    add_client_payload = {
        "id": inbound_id,
        "settings": json.dumps({"clients": [new_client_data]}) 
    }

    add_client_path = "/panel/inbound/addClient" 
    
    logger.info(f"Attempting to add Shadowsocks client via 3x-ui API ({add_client_path}) for inbound {inbound_id}, email: {user_email}")
    logger.debug(f"Payload for addClient: {add_client_payload}")

    add_response_data = await _xui_api_request("POST", add_client_path, json_data=add_client_payload)

    if add_response_data and add_response_data.get("success"):
        logger.info(f"Shadowsocks client added successfully via 3x-ui API. Email: {user_email}")

        inbound_data_fresh = await _xui_api_request("GET", f"/panel/api/inbounds/get/{inbound_id}")

        if not (inbound_data_fresh and inbound_data_fresh.get("success") and inbound_data_fresh.get("obj")):
            logger.error(f"Failed to fetch inbound config {inbound_id} after adding client for link construction. Response: {inbound_data_fresh}")
            return None, user_email

        inbound_obj = inbound_data_fresh.get("obj")
        
        server_address = server_config.get('ip')
        if not server_address:
            logger.error(f"Server IP not found in secrets.SERVERS config for ID {server_config.get('id', 'Unknown')}!")
            server_address = inbound_obj.get("host") # Fallback to inbound host
            if not server_address:
                logger.error(f"Could not find server address from inbound object or secrets.SERVERS for ID {server_config.get('id', 'Unknown')}.")
                return None, user_email

        inbound_port = inbound_obj.get("port")
        if not inbound_port:
            logger.error(f"Could not find inbound port for ID {inbound_id} in API response.")
            return None, user_email

        ss_credentials_raw = f"{ss_method}:{ss_password}"
        encoded_credentials = base64.b64encode(ss_credentials_raw.encode('utf-8')).decode('utf-8').rstrip('=') 
        
        tag = user_email 

        ss_link = f"ss://{encoded_credentials}@{server_address}:{inbound_port}#{tag}"

        logger.info(f"Constructed Shadowsocks link for client {user_email}: {ss_link[:100]}...")
        return ss_link, user_email

    else:
        logger.error(f"Failed to add Shadowsocks client via 3x-ui API. Response: {add_response_data}. Full response: {json.dumps(add_response_data) if add_response_data else 'None'}")
        return None, user_email

async def _xui_delete_vless_client(server_config: dict, client_email: str) -> bool:
    inbound_id = server_config.get("xui_vless_inbound_id")
    if inbound_id is None:
        logger.error(f"3x-ui VLESS inbound ID not configured for server {server_config.get('id', 'Unknown')}. Cannot delete VLESS key via API.")
        return False

    if not client_email:
        logger.error("Cannot delete VLESS client via 3x-ui API: client_email is missing.")
        return False

    api_path = f"/panel/api/inbounds/{inbound_id}/delClient/{client_email}"

    logger.info(f"Deleting VLESS client {client_email} from inbound {inbound_id} via 3x-ui API.")

    response_data = await _xui_api_request("POST", api_path)

    if response_data and response_data.get("success"):
        logger.info(f"VLESS client {client_email} deleted successfully via 3x-ui API.")
        return True
    else:
        logger.error(f"Failed to delete VLESS client {client_email} from inbound {inbound_id} via 3x-ui API. Response: {response_data}")
        error_msg = response_data.get("msg", "").lower() if response_data else ""
        if "not found" in error_msg or "no such" in error_msg or "failed to get client" in error_msg:
            logger.warning(f"3x-ui API reported client {client_email} not found during deletion. Considering deletion successful.")
            return True

        return False

async def _xui_delete_shadowsocks_client(server_config: dict, client_email: str) -> bool:
    inbound_id = server_config.get("xui_shadowsocks_inbound_id")
    if inbound_id is None:
        logger.error(f"3x-ui Shadowsocks inbound ID not configured for server {server_config.get('id', 'Unknown')}. Cannot delete Shadowsocks key via API.")
        return False

    if not client_email:
        logger.error("Cannot delete Shadowsocks client via 3x-ui API: client_email is missing.")
        return False

    api_path = f"/panel/api/inbounds/{inbound_id}/delClient/{client_email}"

    logger.info(f"Deleting Shadowsocks client {client_email} from inbound {inbound_id} via 3x-ui API.")

    response_data = await _xui_api_request("POST", api_path)

    if response_data and response_data.get("success"):
        logger.info(f"Shadowsocks client {client_email} deleted successfully via 3x-ui API.")
        return True
    else:
        logger.error(f"Failed to delete Shadowsocks client {client_email} from inbound {inbound_id} via 3x-ui API. Response: {response_data}")
        error_msg = response_data.get("msg", "").lower() if response_data else ""
        if "not found" in error_msg or "no such" in error_msg or "failed to get client" in error_msg:
            logger.warning(f"3x-ui API reported client {client_email} not found during deletion. Considering deletion successful.")
            return True

        return False

async def _xui_get_client_traffic(server_config: dict, client_email: str) -> Union[dict, None]:

    if not client_email:
        logger.error("Cannot get client traffic via 3x-ui API: client_email is missing.")
        return None

    api_path = f"/panel/api/inbounds/getClientTraffics/{client_email}"

    logger.debug(f"Getting traffic for client {client_email} via 3x-ui API.")

    response_data = await _xui_api_request("GET", api_path)

    if response_data and response_data.get("success") and response_data.get("obj"):
        traffic_data_map = response_data.get("obj", {})
        client_traffic = traffic_data_map.get(client_email)
        if client_traffic:
            logger.debug(f"Traffic data received for {client_email}: Up={client_traffic.get('up')}, Down={client_traffic.get('down')}, Total={client_traffic.get('total')}")
            return {
                "up": client_traffic.get("up", 0),
                "down": client_traffic.get("down", 0),
                "total": client_traffic.get("total", 0),
            }
        else:
            logger.warning(f"Traffic data for client {client_email} not found in API response obj for email {client_email}.")
            return None
    else:
        logger.error(f"Failed to get traffic for client {client_email} via 3x-ui API. Response: {response_data}. Msg: {response_data.get('msg')}")
        return None

async def create_key(server_id: int, protocol: str, user_telegram_id: int, user_username: str | None, total_traffic_gb: Union[int, None] = None) -> Tuple[Union[str, None], Union[str, None]]:

    server_config = _find_server_config(server_id)
    if not server_config:
        logger.error(f"Server config not found for ID: {server_id}")
        return None, None

    if protocol == "outline":
        outline_api_url = server_config.get("outline_api_url")
        if not outline_api_url:
            logger.error(f"Outline API URL not configured for server {server_id}")
            return None, None

        key_name = f"tg_{user_telegram_id}"
        if user_username:
            cleaned_username = ''.join(c if c.isalnum() else '_' for c in user_username).lower()
            key_name += f"_{cleaned_username}"
        key_name += f"_{int(time.time())}" 

        logger.info(f"Creating Outline key via API: {outline_api_url}")
        try:
            response = requests.post(f"{outline_api_url}/access-keys", json={"name": key_name}, verify=False, timeout=15)
            response.raise_for_status()

            if response.status_code == 201:
                key_data_json = response.json()
                key_url = key_data_json.get("accessUrl")
                key_id = key_data_json.get("id")

                if key_url and key_id is not None:
                    logger.info(f"Outline key created successfully. ID: {key_id}, Name: {key_name}")
                    return key_url, str(key_id)
                else:
                    logger.error(f"Outline API returned unexpected data format. Response: {response.text}")
                    return None, None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error connecting to Outline API for server {server_id} during key creation: {e}")
            return None, None
        except Exception as e:
            logger.error(f"An unexpected error occurred during Outline key creation: {e}", exc_info=True)
            return None, None

    elif protocol == "vless":
        inbound_id = server_config.get("xui_vless_inbound_id")
        if inbound_id is None:
            logger.error(f"3x-ui VLESS inbound ID not configured for server {server_id}. Cannot create VLESS key via API.")
            return None, None

        if not all([server_config.get("xui_vless_public_key"), server_config.get("xui_vless_sni"), server_config.get("xui_vless_short_id")]):
            logger.error(f"Missing required Reality parameters (public_key, sni, or short_id) in secrets.py for server {server_id}. Cannot create VLESS Reality key.")
            return None, None

        # Передаем user_username в функцию добавления клиента
        key_data, key_identifier = await _xui_add_vless_client(server_config, user_telegram_id, user_username, total_traffic_gb=total_traffic_gb)

        if key_data and key_identifier:
            logger.info(f"VLESS key created successfully via 3x-ui API for server {server_id}.")
            return key_data, key_identifier
        else:
            logger.error(f"Failed to create VLESS key via 3x-ui API for server {server_id}.")
            return None, key_identifier if key_identifier else None

    elif protocol == "shadowsocks": 
        inbound_id = server_config.get("xui_shadowsocks_inbound_id")
        if inbound_id is None:
            logger.error(f"3x-ui Shadowsocks inbound ID not configured for server {server_id}. Cannot create Shadowsocks key via API.")
            return None, None

        if not server_config.get("xui_shadowsocks_method"):
            logger.error(f"Missing required Shadowsocks method in secrets.py for server {server_id}. Cannot create Shadowsocks key.")
            return None, None

        key_data, key_identifier = await _xui_add_shadowsocks_client(server_config, user_telegram_id, user_username, total_traffic_gb=total_traffic_gb)

        if key_data and key_identifier:
            logger.info(f"Shadowsocks key created successfully via 3x-ui API for server {server_id}.")
            return key_data, key_identifier
        else:
            logger.error(f"Failed to create Shadowsocks key via 3x-ui API for server {server_id}.")
            return None, key_identifier if key_identifier else None


    else:
        logger.error(f"Unknown protocol '{protocol}' requested for key creation.")
        return None, None

async def delete_key(server_id: int, protocol: str, key_identifier: str, key_data: str = None) -> bool:

    server_config = _find_server_config(server_id)
    if not server_config:
        logger.error(f"Server config not found for ID: {server_id}")
        return False

    if protocol == "outline":
        outline_api_url = server_config.get("outline_api_url")
        if not outline_api_url:
            logger.error(f"Outline API URL not configured for server {server_id}")
            return False

        if not key_identifier:
            logger.error(f"Cannot delete Outline key: key_identifier is missing for server {server_id}.")
            return False

        logger.info(f"Deleting Outline key via API. ID: {key_identifier}")
        try:
            target_key_id = int(key_identifier)
            response = requests.delete(f"{outline_api_url}/access-keys/{target_key_id}", verify=False, timeout=15)
            response.raise_for_status()

            if response.status_code == 204: 
                logger.info(f"Outline key {key_identifier} deleted successfully via API.")
                return True
        except ValueError:
            logger.error(f"Invalid Outline key_identifier format for deletion: {key_identifier}. Expected integer ID.")
            return False
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Outline key {key_identifier} not found on the server (already deleted?). Status: 404")
                return True 
            else:
                logger.error(f"HTTP error during Outline key deletion {key_identifier}: {e.response.status_code} - {e.response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error connecting to Outline API for server {server_id} during key deletion: {e}")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during Outline key deletion: {e}", exc_info=True)
            return False

    elif protocol == "vless":
        if not key_identifier:
            logger.error(f"Cannot delete VLESS key: key_identifier (email) is missing for server {server_id}.")
            return False
        return await _xui_delete_vless_client(server_config, key_identifier)

    elif protocol == "shadowsocks": # <-- НОВЫЙ ПРОТОКОЛ SHADOWSOCKS
        if not key_identifier:
            logger.error(f"Cannot delete Shadowsocks key: key_identifier (email) is missing for server {server_id}.")
            return False
        return await _xui_delete_shadowsocks_client(server_config, key_identifier)

    else:
        logger.error(f"Unknown protocol '{protocol}' requested for key deletion.")
        return None, None

def format_bytes(byte_count: Union[int, None]) -> str:
    if byte_count is None:
        return "N/A"
    if byte_count == 0:
        return "0 B"

    unit = 1024
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    power = int(math.log(byte_count, unit))
    power = min(power, len(units) - 1)

    return f"{byte_count / (unit ** power):.2f} {units[power]}"
