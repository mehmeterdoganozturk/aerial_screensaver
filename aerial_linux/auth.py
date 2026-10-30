"""Linux PAM ile güvenli kullanıcı kimlik doğrulama ve kullanıcı bilgileri modülü (Aerial Views)."""

import os
import pwd
import sys
import getpass
import ctypes
import ctypes.util

PAM_PROMPT_ECHO_OFF = 1
PAM_PROMPT_ECHO_ON = 2
PAM_SUCCESS = 0

class PamMessage(ctypes.Structure):
    _fields_ = [("msg_style", ctypes.c_int), ("msg", ctypes.c_char_p)]

class PamResponse(ctypes.Structure):
    _fields_ = [("resp", ctypes.c_void_p), ("resp_retcode", ctypes.c_int)]

class PamHandle(ctypes.Structure):
    pass

PamHandle_p = ctypes.POINTER(PamHandle)

CONV_FUNC = ctypes.CFUNCTYPE(
    ctypes.c_int,
    ctypes.c_int,
    ctypes.POINTER(ctypes.POINTER(PamMessage)),
    ctypes.POINTER(ctypes.POINTER(PamResponse)),
    ctypes.c_void_p
)

class PamConv(ctypes.Structure):
    _fields_ = [("conv", CONV_FUNC), ("appdata_ptr", ctypes.c_void_p)]

libpam = None
libc = None
try:
    libpam_path = ctypes.util.find_library("pam")
    if libpam_path:
        libpam = ctypes.CDLL(libpam_path)
    libc_path = ctypes.util.find_library("c")
    if libc_path:
        libc = ctypes.CDLL(libc_path)
except Exception:
    pass

if libpam and libc:
    libpam.pam_start.restype = ctypes.c_int
    libpam.pam_start.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(PamConv), ctypes.POINTER(PamHandle_p)]
    libpam.pam_authenticate.restype = ctypes.c_int
    libpam.pam_authenticate.argtypes = [PamHandle_p, ctypes.c_int]
    libpam.pam_end.restype = ctypes.c_int
    libpam.pam_end.argtypes = [PamHandle_p, ctypes.c_int]

    libc.calloc.restype = ctypes.c_void_p
    libc.calloc.argtypes = [ctypes.c_size_t, ctypes.c_size_t]
    libc.strdup.restype = ctypes.c_void_p
    libc.strdup.argtypes = [ctypes.c_char_p]


def pam_verify_password(username: str, password: str) -> bool:
    """Kullanıcının sistem parolasını PAM üzerinden doğrular."""
    if not libpam or not libc or not password:
        return False

    def conv_handler(num_msg, msg_p, resp_p, appdata):
        resp_mem = libc.calloc(num_msg, ctypes.sizeof(PamResponse))
        if not resp_mem:
            return 19
        resp_arr = ctypes.cast(resp_mem, ctypes.POINTER(PamResponse))
        resp_p[0] = resp_arr
        for i in range(num_msg):
            msg = msg_p[i].contents
            if msg.msg_style in (PAM_PROMPT_ECHO_OFF, PAM_PROMPT_ECHO_ON):
                resp_arr[i].resp = libc.strdup(password.encode("utf-8"))
                resp_arr[i].resp_retcode = 0
            else:
                resp_arr[i].resp = None
                resp_arr[i].resp_retcode = 0
        return PAM_SUCCESS

    c_conv = CONV_FUNC(conv_handler)
    pam_conv = PamConv(c_conv, None)
    pamh = PamHandle_p()

    res = libpam.pam_start(b"login", username.encode("utf-8"), ctypes.byref(pam_conv), ctypes.byref(pamh))
    if res != PAM_SUCCESS:
        return False

    auth_res = libpam.pam_authenticate(pamh, 0)
    libpam.pam_end(pamh, auth_res)
    return (auth_res == PAM_SUCCESS)


def get_user_info():
    """Mevcut kullanıcının adını, tam adını ve profil resmini döner."""
    user = getpass.getuser()
    try:
        pw = pwd.getpwnam(user)
        full_name = pw.pw_gecos.split(',')[0].strip() or user
    except Exception:
        full_name = user

    avatar_paths = [
        f"/var/lib/AccountsService/icons/{user}",
        os.path.expanduser("~/.face"),
        os.path.expanduser("~/.face.icon"),
    ]
    avatar_path = None
    for p in avatar_paths:
        if os.path.exists(p) and os.path.isfile(p):
            avatar_path = p
            break

    return user, full_name, avatar_path


if __name__ == "__main__":
    # CLI kullanımı: stdin'den parolayı okuyup doğrular
    # python3 -m aerial_linux.auth <username>
    target_user = sys.argv[1] if len(sys.argv) > 1 else getpass.getuser()
    pwd_in = sys.stdin.read().rstrip("\r\n")
    if pam_verify_password(target_user, pwd_in):
        sys.exit(0)
    else:
        sys.exit(1)
