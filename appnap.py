"""Keep macOS from putting the app to sleep (App Nap) while it works.

When the window is minimised or hidden, macOS throttles the app's processor time and timers ("App Nap"): a Build that
takes 1 h can take many hours. NSProcessInfo.beginActivityWithOptions_reason_ with "user initiated" switches App Nap off
for as long as the activity is held (the whole life of the app). The Mac itself may still go to sleep when idle; long
jobs keep it awake with caffeinate (app.Awake). Pure ctypes: no pyobjc in the bundle."""
import ctypes
import ctypes.util
import logging
import subprocess
import sys

USER_INITIATED_ALLOW_SLEEP = 0x00FFFFFF          # NSActivityUserInitiatedAllowingIdleSystemSleep
_token = None


def disable():
    """Start the activity once. Returns True when it is held (always False outside macOS)."""
    global _token
    if sys.platform != "darwin" or _token is not None:
        return _token is not None
    try:                                              # also as a user default (read at the next start)
        subprocess.run(["defaults", "write", "com.moneymakingmachine.app", "NSAppSleepDisabled", "-bool", "YES"],
                       capture_output=True, timeout=5)
    except Exception:
        pass
    try:
        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Foundation.framework/Foundation")
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc") or "/usr/lib/libobjc.A.dylib")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        addr = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value

        def msg(*types):                              # objc_msgSend with exact argument types (arm64 needs them)
            return ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, *types)(addr)
        cls, sel = objc.objc_getClass, objc.sel_registerName
        info = msg()(cls(b"NSProcessInfo"), sel(b"processInfo"))
        reason = msg(ctypes.c_char_p)(cls(b"NSString"), sel(b"stringWithUTF8String:"),
                                      b"MoneyMakingMachine analyses footage")
        tok = msg(ctypes.c_uint64, ctypes.c_void_p)(info, sel(b"beginActivityWithOptions:reason:"),
                                                     USER_INITIATED_ALLOW_SLEEP, reason)
        if not tok:
            return False
        _token = msg()(tok, sel(b"retain"))            # held until the app quits
        logging.info("app nap disabled")
        return True
    except Exception:
        logging.exception("could not disable App Nap")
        return False
