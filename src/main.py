"""Main entry point for Sakura Flow application with TG Proxy."""
import sys
import os
import logging
import threading
import time
from pathlib import Path

try:
    import win32api
    import win32con
    import win32gui
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).resolve().parent
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    internal_dir = BASE_DIR / "_internal"
    if str(internal_dir) not in sys.path:
        sys.path.insert(0, str(internal_dir))
else: 
    file_path = Path(__file__).resolve()
    BASE_DIR = file_path.parent.parent
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

try:
    import src  
    sys.modules['src'] = src
    from src import admin, ui, config, service, tools, state
except ImportError:
    import admin, ui, config, service, tools, state

try:
    import tg_ws_proxy 
except ImportError:
    try:
        from src import tg_ws_proxy
    except ImportError:
        tg_ws_proxy = None

logging.basicConfig(
    filename=config.LOG_FILE,
    filemode="w",
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

def start_proxy_thread():
    return tools.start_socks5_proxy()


def stop_proxy_thread():
    tools.stop_socks5_proxy()

_current_bat = None
_restart_func = None

def on_wake():
    global _current_bat, _restart_func
    logging.info("Компьютер проснулся! Проверяю службу...")
    
    if _current_bat and _restart_func:
        time.sleep(2)
        try:
            service.stop_service()
            time.sleep(1)
            _restart_func()
            logging.info("Служба перезапущена после пробуждения")
        except Exception as e:
            logging.error(f"Ошибка перезапуска службы: {e}")
    
    app_state = state.load_state()
    if app_state.get("socks5_enabled", False):
        time.sleep(3)
        try:
            stop_proxy_thread()
            time.sleep(1)
            start_proxy_thread()
            logging.info("Прокси перезапущен после пробуждения")
        except Exception as e:
            logging.error(f"Ошибка перезапуска прокси: {e}")

def register_sleep_handler(restart_func, current_bat):
    global _current_bat, _restart_func
    _current_bat = current_bat
    _restart_func = restart_func
    
    if not HAS_WIN32:
        logging.info("win32api не установлен, обработка сна недоступна")
        return
    
    try:
        def WndProc(hwnd, msg, wParam, lParam):
            if msg == win32con.WM_POWERBROADCAST:
                if wParam == win32con.PBT_APMRESUMEAUTOMATIC:
                    logging.info("Событие пробуждения!")
                    threading.Thread(target=on_wake, daemon=True).start()
            return win32gui.DefWindowProc(hwnd, msg, wParam, lParam)
        
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = WndProc
        wc.lpszClassName = "SakuraFlowPower"
        win32gui.RegisterClass(wc)
        hwnd = win32gui.CreateWindow("SakuraFlowPower", "SakuraFlow", 0, 0, 0, 0, 0, 0, 0, 0, None)
        
        logging.info("Обработчик сна зарегистрирован")
    except Exception as e:
        logging.error(f"Ошибка регистрации обработчика сна: {e}")

def main():
    logging.info(f"START SAKURA FLOW. CWD: {os.getcwd()}")
    
    if not admin.is_admin():
        logging.info("Запрос прав администратора...")
        admin.run_as_admin()
        return
    
    tools.start_auto_monitor()
    
    app_state = state.load_state()
    if app_state.get("socks5_enabled", False):
        logging.info("[SOCKS5] Восстановление прокси после запуска")
        start_proxy_thread()
    
    bat_files = [
        f for f in config.BAT_DIR.glob("*.bat") 
        if f.name.lower() not in ["service.bat", "general.bat"]
    ]
    
    exit_code = ui.create_tray_app(bat_files, register_sleep_handler)
    
    tools.stop_auto_monitor()
    stop_proxy_thread()
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
