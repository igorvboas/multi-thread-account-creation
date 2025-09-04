import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import src.anti_detection as ad
from loguru import logger
import time
from typing import Dict, Optional
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

class BrowserHandler:
    """Classe para gerenciar a instância do navegador com anti-detecção."""
    def __init__(self, thread_id: int, ad: ad.AntiDetection, proxy: Optional[Dict] = None, headless: bool = False):
        self.thread_id = thread_id
        self.ad = ad
        self.proxy = proxy
        self.headless = headless
        self.driver = None
        self.logger = logger  # Adicione esta linha
        
        logger.info("BrowserHandler inicializado para Thread {}", self.thread_id)
        
        # Inicializar o driver com tratamento de erro
        try:
            self.driver = self.ad.get_undetected_driver(proxy=self.proxy, headless=self.headless)
            if self.driver is None:
                raise Exception("Driver retornou None")
            logger.info("Thread {}: Driver inicializado com sucesso.", self.thread_id)
        except Exception as e:
            logger.error("Thread {}: Erro ao inicializar driver: {}", self.thread_id, e)
            raise Exception(f"Falha ao inicializar driver: {e}")
        

    def _wait_for_element(self, xpath: str, timeout: int = 10):
        """Aguarda elemento por XPath com WebDriverWait."""
        if not self.driver:
            self.logger.error("Thread {}: Navegador não inicializado.", self.thread_id)
            raise Exception("Navegador não inicializado.")
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            self.logger.debug("Thread {}: Elemento encontrado por XPath: {}", self.thread_id, xpath)
            return element
        except Exception as e:
            self.logger.warning("Thread {}: Elemento não encontrado por XPath '{}': {}", self.thread_id, xpath, e)
            return None
    
    def navigate(self, url: str):
        """Navega para uma URL com verificação de driver."""
        if self.driver is None:
            raise Exception(f"Thread {self.thread_id}: Driver não inicializado")
        
        try:
            logger.info("Thread {}: Navegando para {}", self.thread_id, url)
            self.driver.get(url)
            self.ad.sleep_with_jitter()
            
            # Resto do código do método navigate()...
            
        except Exception as e:
            logger.error("Thread {}: Erro ao navegar para {}: {}", self.thread_id, url, e)
            raise

    def find_element(self, by, value):
        if not self.driver:
            logger.error("Thread {}: Navegador não inicializado.", self.thread_id)
            raise Exception("Navegador não inicializado.")
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                element = self.driver.find_element(by, value)
                logger.debug("Thread {}: Elemento encontrado: {}", self.thread_id, value)
                return element
            except Exception as e:
                logger.warning("Thread {}: Tentativa {} falhou: {}", self.thread_id, attempt + 1, e)
                self.ad.sleep_with_jitter(1, 3)
        raise Exception(f"Elemento {value} não encontrado após {max_attempts} tentativas.")

    def human_like_input(self, element, text: str):
        if not self.driver:
            logger.error("Thread {}: Navegador não inicializado.", self.thread_id)
            raise Exception("Navegador não inicializado.")
        logger.debug("Thread {}: Preenchendo campo com: {}", self.thread_id, text)
        self.ad.human_like_type(element, text)

    def close(self):
        if self.driver:
            logger.info("Thread {}: Fechando navegador.", self.thread_id)
            self.driver.quit()
            self.driver = None
            logger.info("Thread {}: Browser fechado com sucesso", self.thread_id)
        else:
            logger.warning("Thread {}: Browser já estava fechado ou não inicializado", self.thread_id)

    def __del__(self):
        self.close()

if __name__ == "__main__":
    ad_instance = ad.AntiDetection()
    browser = BrowserHandler(thread_id=1, ad=ad_instance, proxy=None, headless=False)
    try:
        browser.navigate("https://www.instagram.com")
        time.sleep(5)
    finally:
        browser.close()