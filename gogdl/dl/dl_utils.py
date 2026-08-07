import json
import zlib
import os
import gogdl.constants as constants
from gogdl.dl.objects import v1, v2
import shutil
import time
import requests
from sys import exit, platform

PATH_SEPARATOR = os.sep
TIMEOUT = 10


def get_json(api_handler, url):
    x = api_handler.session.get(url, headers={"Accept": "application/json"})
    if not x.ok:
        return
    return x.json()


def get_zlib_encoded(api_handler, url):
    retries = 5
    while retries > 0:
        try:
            x = api_handler.session.get(url, timeout=TIMEOUT)
            if not x.ok:
                return None, None
            try:
                decompressed = json.loads(zlib.decompress(x.content, 15))
            except zlib.error:
                return x.json(), x.headers
            return decompressed, x.headers
        except Exception:
            time.sleep(2)
            retries-=1
    return None, None


def prepare_location(path, logger=None):
    os.makedirs(path, exist_ok=True)
    if logger:
        logger.debug(f"Created directory {path}")


# V1 Compatible
def galaxy_path(manifest: str):
    galaxy_path = manifest
    if galaxy_path.find("/") == -1:
        galaxy_path = manifest[0:2] + "/" + manifest[2:4] + "/" + galaxy_path
    return galaxy_path


SECURE_LINK_ATTEMPTS = 8


def get_secure_link(api_handler, path, gameId, generation=2, logger=None, root=None):
    """Fetch the CDN links for a depot path.

    This used to retry by calling itself — with no attempt limit, no backoff, and the
    `root` argument dropped on every recursive call. Any failure that did not clear on
    its own therefore became a permanent, silent hang: the process sat in a 0.2s loop
    re-asking forever, the download never started, no error was ever reported, and from
    the outside it looked exactly like a download frozen at a percentage. That is the
    stall seen on an 18 GB game, caught with a stack 27 frames deep in this function.

    An expired access token is the most likely trigger and used to be unrecoverable
    here: GOG tokens last an hour, a large download does not, and a 401 was retried
    verbatim forever rather than refreshing. Now the token is refreshed once on a 401,
    the retries are bounded and backed off, and running out raises instead of hanging.
    """
    url = ""
    if generation == 2:
        url = f"{constants.GOG_CONTENT_SYSTEM}/products/{gameId}/secure_link?_version=2&generation=2&path={path}"
    elif generation == 1:
        url = f"{constants.GOG_CONTENT_SYSTEM}/products/{gameId}/secure_link?_version=2&type=depot&path={path}"
    if root:
        url += f"&root={root}"

    refreshed = False
    last_error = "unknown error"

    for attempt in range(SECURE_LINK_ATTEMPTS):
        if attempt:
            # 0.5s, 1s, 2s, 4s … capped. A tight loop against an endpoint that is
            # rate-limiting is the surest way to stay rate-limited.
            time.sleep(min(0.5 * (2 ** (attempt - 1)), 15))

        try:
            r = requests.get(url, headers=api_handler.session.headers, timeout=TIMEOUT)
        except BaseException as exception:
            last_error = f"{type(exception).__name__}: {exception}"
            if logger:
                logger.warning(f"secure link attempt {attempt + 1}/{SECURE_LINK_ATTEMPTS} failed: {last_error}")
            continue

        if r.status_code == 200:
            return r.json()['urls']

        last_error = f"HTTP {r.status_code}"

        # A large download outlives its access token. Refresh once, then carry on with
        # the remaining attempts rather than spinning on a 401 that can never succeed.
        if r.status_code in (401, 403) and not refreshed:
            refreshed = True
            try:
                if api_handler.auth_manager.refresh_credentials():
                    credentials = api_handler.auth_manager.get_credentials()
                    api_handler.session.headers["Authorization"] = f"Bearer {credentials['access_token']}"
                    if logger:
                        logger.info("access token expired mid-download — refreshed")
                    continue
            except BaseException as exception:
                last_error = f"token refresh failed: {exception}"

        if logger:
            logger.warning(f"secure link attempt {attempt + 1}/{SECURE_LINK_ATTEMPTS}: {last_error}")

    raise RuntimeError(
        f"Could not get download links for {gameId} after {SECURE_LINK_ATTEMPTS} attempts ({last_error})."
    )

def get_dependency_link(api_handler):
    data = get_json(
        api_handler,
        f"{constants.GOG_CONTENT_SYSTEM}/open_link?generation=2&_version=2&path=/dependencies/store/",
    )
    if not data:
        return None
    return data["urls"]


def merge_url_with_params(url, parameters):
    for key in parameters.keys():
        url = url.replace("{" + key + "}", str(parameters[key]))
        if not url:
            print(f"Error ocurred getting a secure link: {url}")
    return url


def parent_dir(path: str):
    return os.path.split(path)[0]


def calculate_sum(path, function, read_speed_function=None):
    with open(path, "rb") as f:
        calculate = function()
        while True:
            chunk = f.read(16 * 1024)
            if not chunk:
                break
            if read_speed_function:
                read_speed_function(len(chunk))
            calculate.update(chunk)

        return calculate.hexdigest()


def get_readable_size(size):
    power = 2 ** 10
    n = 0
    power_labels = {0: "", 1: "K", 2: "M", 3: "G"}
    while size > power:
        size /= power
        n += 1
    return size, power_labels[n] + "B"


def check_free_space(size: int, path: str):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    _, _, available_space = shutil.disk_usage(path)

    return size < available_space


def get_range_header(offset, size):
    from_value = offset
    to_value = (int(offset) + int(size)) - 1
    return f"bytes={from_value}-{to_value}"

# Creates appropriate Manifest class based on provided meta from json
def create_manifest_class(meta: dict, api_handler):
    version = meta.get("version") 
    if version == 1:
        return v1.Manifest.from_json(meta, api_handler)
    else:
        return v2.Manifest.from_json(meta, api_handler)

def get_case_insensitive_name(path):
    if platform == "win32" or os.path.exists(path):
        return path
    root = path
    # Find existing directory
    while not os.path.exists(root):
        root = os.path.split(root)[0]
    
    if not root[len(root) - 1] in ["/", "\\"]:
        root = root + os.sep
    # Separate unknown path from existing one
    s_working_dir = path.replace(root, "").split(os.sep)
    paths_to_find = len(s_working_dir)
    paths_found = 0
    for directory in s_working_dir:
        if not os.path.exists(root):
            break
        dir_list = os.listdir(root)
        found = False
        for existing_dir in dir_list:
            if existing_dir.lower() == directory.lower():
                root = os.path.join(root, existing_dir)
                paths_found += 1
                found = True
        if not found:
            root = os.path.join(root, directory)
            paths_found += 1

    if paths_to_find != paths_found:
        root = os.path.join(root, os.sep.join(s_working_dir[paths_found:]))
    return root

