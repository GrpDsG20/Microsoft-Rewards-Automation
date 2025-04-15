import os
import sys
import json
import random
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import time
from datetime import datetime

class Config:
    DEFAULT_CONFIG = {
        "search_delay": (3, 7),
        "page_load_timeout": 30,
        "max_retries": 3,
        "save_log": True,
        "headless_mode": False
    }
    
    @classmethod
    def get_config_path(cls):
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(application_path, 'config.json')

    @classmethod
    def load(cls):
        try:
            with open(cls.get_config_path(), 'r') as f:
                return {**cls.DEFAULT_CONFIG, **json.load(f)}
        except FileNotFoundError:
            return cls.DEFAULT_CONFIG
        except Exception as e:
            logging.error(f"Error cargando configuración: {str(e)}")
            return cls.DEFAULT_CONFIG

    @classmethod
    def save(cls, config):
        try:
            with open(cls.get_config_path(), 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            logging.error(f"Error guardando configuración: {str(e)}")

def get_log_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'logs')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')

class BingSearchAutomation:
    def __init__(self, status_callback=None):
        self.config = Config.load()
        self.status_callback = status_callback
        self.running = True
        self.setup_logging()

    def setup_logging(self):
        if self.config['save_log']:
            log_dir = get_log_path()
            os.makedirs(log_dir, exist_ok=True)
            log_filename = os.path.join(log_dir, f"search_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
            logging.basicConfig(
                filename=log_filename,
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s'
            )

    def update_status(self, message):
        logging.info(message)
        if self.status_callback:
            self.status_callback(message)

    def setup_driver(self, driver_path):
        options = Options()
        if self.config['headless_mode']:
            options.add_argument('--headless')
        options.add_argument('--start-maximized')
        options.add_argument('--disable-extensions')
        options.page_load_strategy = 'eager'
        
        try:
            service = Service(driver_path)
            driver = webdriver.Edge(service=service, options=options)
            driver.set_page_load_timeout(self.config['page_load_timeout'])
            return driver
        except Exception as e:
            raise Exception(f"Error al configurar WebDriver: {str(e)}")

    def perform_search(self, search_file, driver_path):
        if not all([os.path.isfile(f) for f in [search_file, driver_path]]):
            raise FileNotFoundError("Archivo de búsquedas o WebDriver no encontrado")

        try:
            with open(search_file, 'r', encoding='utf-8') as f:
                searches = [line.strip() for line in f if line.strip()]
        except Exception as e:
            raise Exception(f"Error leyendo archivo de búsquedas: {str(e)}")

        if not searches:
            raise ValueError("El archivo de búsquedas está vacío")

        driver = None
        completed_searches = 0
        
        try:
            driver = self.setup_driver(driver_path)
            
            for i, search_term in enumerate(searches, 1):
                if not self.running:
                    self.update_status("Proceso cancelado por el usuario")
                    break
                    
                retries = 0
                while retries < self.config['max_retries'] and self.running:
                    try:
                        self.single_search(driver, search_term, i, len(searches))
                        completed_searches += 1
                        break
                    except TimeoutException:
                        retries += 1
                        self.update_status(f"Timeout en '{search_term}'. Reintento {retries}/{self.config['max_retries']}")
                        if retries == self.config['max_retries']:
                            logging.error(f"Fallo al completar búsqueda para '{search_term}' después de {retries} reintentos")
                    except WebDriverException as e:
                        logging.error(f"Error de WebDriver: {str(e)}")
                        raise

        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            self.update_status(f"Completadas {completed_searches}/{len(searches)} búsquedas")

    def single_search(self, driver, search_term, current, total):
        driver.get("https://www.bing.com")
        
        wait = WebDriverWait(driver, 10)
        search_box = wait.until(
            EC.presence_of_element_located((By.NAME, "q"))
        )
        
        search_box.clear()
        search_box.send_keys(search_term)
        search_box.send_keys(Keys.RETURN)
        
        delay = random.uniform(*self.config['search_delay'])
        self.update_status(f"Buscando ({current}/{total}): {search_term}")
        time.sleep(delay)

class SearchAutomationGUI:
    def __init__(self):
        try:
            self.root = tk.Tk()
            self.root.title("Automatización de Búsquedas Bing")
            self.root.geometry("600x400")
            
            # Estilo
            self.style = ttk.Style()
            self.style.configure("Accent.TButton", foreground="white", background="green")
            self.style.configure("Cancel.TButton", foreground="white", background="red")
            
            self.automation = BingSearchAutomation(self.update_status)
            self.setup_gui()
        except Exception as e:
            messagebox.showerror("Error de Inicialización", f"Error iniciando la aplicación: {str(e)}")
            if hasattr(self, 'root') and self.root:
                self.root.destroy()
            sys.exit(1)

    def setup_gui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.create_file_selection(main_frame)
        self.create_config_frame(main_frame)
        self.create_status_frame(main_frame)
        self.create_copyright_label(main_frame)
        
        # Configurar pesos de grid
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

    def create_file_selection(self, parent):
        files_frame = ttk.LabelFrame(parent, text="Selección de Archivos", padding="5")
        files_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)

        ttk.Label(files_frame, text="Archivo de Búsquedas:").grid(row=0, column=0, sticky="w")
        self.search_file_entry = ttk.Entry(files_frame, width=50)
        self.search_file_entry.grid(row=0, column=1, padx=5)
        ttk.Button(files_frame, text="Examinar", command=lambda: self.browse_file(self.search_file_entry)).grid(row=0, column=2)

        ttk.Label(files_frame, text="Archivo WebDriver:").grid(row=1, column=0, sticky="w")
        self.driver_file_entry = ttk.Entry(files_frame, width=50)
        self.driver_file_entry.grid(row=1, column=1, padx=5)
        ttk.Button(files_frame, text="Examinar", command=lambda: self.browse_file(self.driver_file_entry)).grid(row=1, column=2)

    def create_config_frame(self, parent):
        config_frame = ttk.LabelFrame(parent, text="Configuración", padding="5")
        config_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)

        self.headless_var = tk.BooleanVar(value=self.automation.config['headless_mode'])
        ttk.Checkbutton(config_frame, text="Modo sin cabeza (Headless)", variable=self.headless_var).grid(row=0, column=0)

        # Frame para botones
        buttons_frame = ttk.Frame(config_frame)
        buttons_frame.grid(row=0, column=1, sticky="e")
        
        ttk.Button(buttons_frame, text="Iniciar", command=self.start_search, style="Accent.TButton").grid(row=0, column=0, padx=5)
        ttk.Button(buttons_frame, text="Cancelar", command=self.cancel_search, style="Cancel.TButton").grid(row=0, column=1)

    def create_status_frame(self, parent):
        status_frame = ttk.LabelFrame(parent, text="Estado", padding="5")
        status_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)

        self.status_label = ttk.Label(status_frame, text="Listo")
        self.status_label.grid(row=0, column=0, sticky="w")

        self.progress = ttk.Progressbar(status_frame, mode='indeterminate')
        self.progress.grid(row=1, column=0, sticky="ew", pady=5)

    def create_copyright_label(self, parent):
        copyright_label = ttk.Label(parent, text="© 2025 Smite. Todos los derechos reservados.", font=("Helvetica", 8))
        copyright_label.grid(row=3, column=0, columnspan=2, sticky="s", pady=5)

    def browse_file(self, entry_field):
        file_path = filedialog.askopenfilename(filetypes=[("Archivos de Texto", "*.txt"), ("Todos los Archivos", "*.*")])
        if file_path:
            entry_field.delete(0, tk.END)
            entry_field.insert(0, file_path)

    def update_status(self, message):
        self.status_label.config(text=message)
        self.root.update()

    def start_search(self):
        search_file = self.search_file_entry.get()
        driver_path = self.driver_file_entry.get()

        if not search_file or not driver_path:
            messagebox.showerror("Error", "Por favor seleccione ambos archivos (búsquedas y WebDriver)")
            return

        self.automation.config['headless_mode'] = self.headless_var.get()
        Config.save(self.automation.config)
        
        # Reiniciar estado de ejecución
        self.automation.running = True

        try:
            self.progress.start()
            self.automation.perform_search(search_file, driver_path)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            logging.error(f"Error durante la búsqueda: {str(e)}")
        finally:
            self.progress.stop()

    def cancel_search(self):
        self.automation.running = False
        self.update_status("Cancelando... Por favor espere")

    def run(self):
        try:
            self.root.mainloop()
        except Exception as e:
            messagebox.showerror("Error", f"Error en la aplicación: {str(e)}")
            logging.error(f"Error en la aplicación: {str(e)}")

if __name__ == "__main__":
    try:
        app = SearchAutomationGUI()
        app.run()
    except Exception as e:
        messagebox.showerror("Error Fatal", f"Error fatal: {str(e)}")
        logging.error(f"Error fatal: {str(e)}")
        sys.exit(1)