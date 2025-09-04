"""
Configurações para execução multithread do criador de contas Instagram
"""

import os
import threading
from dataclasses import dataclass
from typing import Dict, Any

# Variáveis globais para caminhos dos arquivos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # sobe 1 nível (project_root)

CONFIG_DIR = os.path.join(BASE_DIR, "config")
SCRIPT_DIR = os.path.join(BASE_DIR, "src")
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, 'screenshots')

PROXY_CSV_FILE = os.path.join(CONFIG_DIR, 'proxies.csv')
ACCOUNTS_CSV_FILE = os.path.join(CONFIG_DIR, 'accounts_data.csv')

@dataclass
class ThreadConfig:
    """Configurações para cada thread de automação."""
    
    # Configurações de Thread
    MAX_THREADS: int = 30
    THREAD_TIMEOUT: int = 300  # 5 minutos por thread
    
    # Configurações de Timing
    PAGE_LOAD_TIMEOUT: int = 30
    ELEMENT_WAIT_TIMEOUT: int = 20
    EMAIL_CHECK_RETRIES: int = 5
    EMAIL_CHECK_INTERVAL: int = 15  # segundos
    
    # Configurações de Arquivos
    PROXIES_FILE: str = os.path.join(SCRIPT_DIR, "proxies.csv")
    ACCOUNTS_FILE: str = os.path.join(SCRIPT_DIR, "accounts_data.csv")
    OUTPUT_FILE: str = os.path.join(DATA_DIR, "accounts_created.csv")
    LOGS_DIR: str = LOGS_DIR
    DATA_DIR: str = DATA_DIR
    
    # Configurações do Instagram
    INSTAGRAM_SIGNUP_URL: str = "https://www.instagram.com/accounts/emailsignup/"
    INSTAGRAM_VERIFICATION_SENDER: str = "no-reply@mail.instagram.com"
    
    # Configurações de Retry
    MAX_RETRY_ATTEMPTS: int = 2
    RETRY_DELAY: int = 5  # segundos entre tentativas
    
    # Configurações de Screenshot
    SAVE_SCREENSHOTS: bool = True
    SCREENSHOT_DIR: str = SCREENSHOTS_DIR
    
    def __post_init__(self):
        """Cria diretórios necessários."""
        os.makedirs(self.LOGS_DIR, exist_ok=True)
        os.makedirs(self.DATA_DIR, exist_ok=True)
        if self.SAVE_SCREENSHOTS:
            os.makedirs(self.SCREENSHOT_DIR, exist_ok=True)

class ProxyRotator:
    """Gerencia rotação de proxies entre threads."""
    
    def __init__(self, proxies: list):
        self.proxies = proxies
        self.current_index = 0
        self.lock = threading.Lock()
    
    def get_next_proxy(self):
        """Retorna o próximo proxy na rotação."""
        with self.lock:
            if not self.proxies:
                return None
            
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            return proxy

class ThreadStats:
    """Coleta estatísticas de execução das threads."""
    
    def __init__(self):
        self.stats = {
            'total_attempts': 0,
            'successful_creations': 0,
            'failed_creations': 0,
            'proxy_errors': 0,
            'verification_timeouts': 0,
            'browser_errors': 0,
            'execution_time': 0,
            'threads_used': 0
        }
        self.lock = threading.Lock()
    
    def increment(self, key: str, value: int = 1):
        """Incrementa uma estatística de forma thread-safe."""
        with self.lock:
            if key in self.stats:
                self.stats[key] += value
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna cópia das estatísticas atuais."""
        with self.lock:
            return self.stats.copy()
    
    def get_success_rate(self) -> float:
        """Calcula taxa de sucesso."""
        if self.stats['total_attempts'] == 0:
            return 0.0
        return (self.stats['successful_creations'] / self.stats['total_attempts']) * 100

# Instância global de configuração
CONFIG = ThreadConfig()

# Mapeamento de códigos de erro para facilitar debugging
ERROR_CODES = {
    'PROXY_ERROR': 'Erro de conexão com proxy',
    'BROWSER_INIT_ERROR': 'Falha ao inicializar browser',
    'PAGE_LOAD_ERROR': 'Erro ao carregar página do Instagram',
    'FORM_FILL_ERROR': 'Erro ao preencher formulário',
    'VERIFICATION_TIMEOUT': 'Timeout ao aguardar código de verificação',
    'EMAIL_CONNECTION_ERROR': 'Erro de conexão com Gmail',
    'ELEMENT_NOT_FOUND': 'Elemento da página não encontrado',
    'UNKNOWN_ERROR': 'Erro desconhecido'
}

def get_error_message(error_code: str) -> str:
    """Retorna mensagem amigável para código de erro."""
    return ERROR_CODES.get(error_code, ERROR_CODES['UNKNOWN_ERROR'])


import threading