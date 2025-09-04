import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import src.browser_handler as bh
import src.anti_detection as ad
from src.browser_handler import BrowserHandler
from loguru import logger
import time
import csv
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from typing import Dict, List, Tuple
import json
from dotenv import load_dotenv
import imaplib
import email
import re
from gmail_reader import GmailReader
from dataclasses import dataclass
from queue import Queue
from thread_config import CONFIG

load_dotenv()

# Variáveis globais para caminhos dos arquivos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # sobe 1 nível (project_root)

CONFIG_DIR = os.path.join(BASE_DIR, "config")
SCRIPT_DIR = os.path.join(BASE_DIR, "src")
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
# SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

PROXY_CSV_FILE = os.path.join(CONFIG_DIR, 'proxies.csv')
ACCOUNTS_CSV_FILE = os.path.join(CONFIG_DIR, 'accounts_data.csv')

USE_PROXIES = True   # mude para True quando quiser testar com proxy

# Criar diretórios se não existirem
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

@dataclass
class ProxyConfig:
    ip: str
    port: int
    username: str
    password: str
    country: str
    city: str

@dataclass
class AccountData:
    email: str
    full_name: str
    username: str
    password: str

class ThreadSafeAccountCreator:
    """Versão thread-safe do AccountCreator para execução paralela."""
    
    def __init__(self, thread_id: int, proxy: ProxyConfig):
        self.thread_id = thread_id
        self.proxy = proxy
        self.browser = None
        self.wait = None
        self.driver = None  # Adicionar esta linha
        self.signup_url = "https://www.instagram.com/accounts/emailsignup/"
        self.gmail_server = os.getenv("GMAIL_SERVER", "imap.gmail.com")
        self.gmail_username = os.getenv("GMAIL_USERNAME")
        self.gmail_password = os.getenv("GMAIL_PASSWORD")
        self.lock = threading.Lock()
        self.headless = False  # Mantenha como False para depuração
        
        # Configura log específico para esta thread
        log_file = os.path.join(LOGS_DIR, f"thread_{thread_id}.log")
        logger.add(log_file, level="INFO", format="Thread {thread} | {time} | {level} | {message}")
        p = f"{proxy.ip}:{proxy.port}" if proxy else "SEM PROXY"
        logger.info("Thread {} inicializada com proxy {}", thread_id, p)
        
        # Inicializar o browser APENAS UMA VEZ aqui
        try:
            self.initialize_browser()
            if not self.browser or not self.driver:
                raise Exception("Falha na inicialização do browser")
            logger.info("Thread {}: Inicialização completa com sucesso", self.thread_id)
        except Exception as e:
            logger.error("Thread {}: Erro crítico na inicialização: {}", self.thread_id, e)
            self.cleanup()
            raise

        
    
    def configure_proxy_if_needed(self):
        """Configura e inicializa o BrowserHandler com o proxy da thread."""
        try:
            if self.proxy:
                proxy_str = f"{self.proxy.ip}:{self.proxy.port}"
                logger.info("Thread {} aplicando proxy: {}", self.thread_id, proxy_str)
                self.browser = BrowserHandler(proxy={
                    "ip": self.proxy.ip,
                    "port": self.proxy.port,
                    "username": self.proxy.username,
                    "password": self.proxy.password,
                }, headless=self.headless)
            else:
                logger.info("Thread {} sem proxy definido, iniciando navegador local.", self.thread_id)
                self.browser = BrowserHandler(headless=self.headless)
            return True
        except Exception as e:
            logger.error("Thread {}: erro ao configurar proxy: {}", self.thread_id, e)
            self.browser = None
            return False


    def cleanup(self):
        """Limpa recursos de forma segura."""
        try:
            if self.browser:
                self.browser.close()
                self.browser = None
            self.driver = None
            self.wait = None
            logger.info("Thread {}: Cleanup realizado com sucesso", self.thread_id)
        except Exception as e:
            logger.error("Thread {}: Erro durante cleanup: {}", self.thread_id, e)

    def initialize_browser(self):
        """Inicializa o browser com proxy e headless - CHAMADO APENAS UMA VEZ."""
        try:
            ad_instance = ad.AntiDetection()
            proxy_dict = self.proxy.__dict__ if self.proxy else None
            
            self.browser = BrowserHandler(
                thread_id=self.thread_id, 
                ad=ad_instance, 
                proxy=proxy_dict, 
                headless=self.headless
            )
            
            # Armazenar referência do driver
            self.driver = self.browser.driver
            
            # Configurar WebDriverWait
            self.wait = WebDriverWait(self.driver, CONFIG.ELEMENT_WAIT_TIMEOUT)
            
            logger.info("Thread {}: Browser inicializado com sucesso", self.thread_id)
            return True
            
        except Exception as e:
            logger.error("Thread {}: Erro ao inicializar browser: {}", self.thread_id, e)
            self.browser = None
            self.driver = None
            self.wait = None
            return False
        

    def create_account_old(self, account: AccountData) -> bool:
        """Cria uma nova conta no Instagram."""
        logger.info("Thread {}: Iniciando criação de conta: {} | {}", 
                   self.thread_id, account.username, account.email)
        try:
            #if not self.initialize_browser():
            #    return False
            # ADICIONAR verificação se browser está funcionando
            if not self.driver:
                logger.error("Thread {}: Browser não inicializado", self.thread_id)
                return False

            logger.info("Thread {}: Navegando para: {}", self.thread_id, self.signup_url)
            self.browser.navigate(self.signup_url)

            logger.info("Thread {}: URL atual após navegação: {}", 
                       self.thread_id, self.browser.driver.current_url)
            time.sleep(5)

            # Aguardar página de signup
            self._wait_for_signup_page()

            # Preencher formulário principal
            logger.info("Thread {}: Preenchendo formulário de cadastro...", self.thread_id)
            
            email_field = self._wait_for_element("//input[@name='emailOrPhone']")
            self.browser.human_like_input(email_field, account.email)

            name_field = self._wait_for_element("//input[@name='fullName']")
            self.browser.human_like_input(name_field, account.full_name)

            username_field = self._wait_for_element("//input[@name='username']")
            self.browser.human_like_input(username_field, account.username)

            password_field = self._wait_for_element("//input[@name='password']")
            self.browser.human_like_input(password_field, account.password)

            # Submeter formulário
            submit_button = self._wait_for_element("//button[@type='submit' and not(@disabled)]")
            submit_button.click()
            self.browser.ad.sleep_with_jitter(5, 10)

            # Preencher data de nascimento
            if self._fill_birthdate():
                # Aguardar e confirmar código de verificação
                code = self._get_verification_code(account.email)
                if code and self._confirm_verification_code(code):
                    self._save_account(account, "success", self.browser.anti.generate_fingerprint())
                    logger.info("Thread {}: Conta criada com sucesso: {}", self.thread_id, account.username)
                    return True

            self._save_account(account, "failed", self.browser.anti.generate_fingerprint())
            return False

        except Exception as e:
            logger.error("Thread {}: Erro ao criar conta: {}", self.thread_id, e)
            self._save_account(account, "failed", {})
            return False
        finally:
            self.close_browser()

    def create_account(self, account: AccountData) -> bool:
        """Cria uma nova conta no Instagram."""
        logger.info("Thread {}: Iniciando criação de conta: {} | {}", 
                self.thread_id, account.username, account.email)
        try:
            # VERIFICAR se o browser já foi inicializado (não inicializar novamente)
            if not self.browser or not self.driver:
                logger.error("Thread {}: Browser não está inicializado", self.thread_id)
                return False

            logger.info("Thread {}: Navegando para: {}", self.thread_id, self.signup_url)
            self.browser.navigate(self.signup_url)
            logger.info("Thread {}: URL atual após navegação: {}", 
                    self.thread_id, self.driver.current_url)
            time.sleep(10)

            # Aguardar página de signup
            self._wait_for_signup_page()

            # Preencher formulário principal
            logger.info("Thread {}: Preenchendo formulário de cadastro...", self.thread_id)
            
            email_field = self._wait_for_element("//input[@name='emailOrPhone']")
            self.browser.human_like_input(email_field, account.email)

            name_field = self._wait_for_element("//input[@name='fullName']")
            self.browser.human_like_input(name_field, account.full_name)

            username_field = self._wait_for_element("//input[@name='username']")
            self.browser.human_like_input(username_field, account.username)

            password_field = self._wait_for_element("//input[@name='password']")
            self.browser.human_like_input(password_field, account.password)

            # Submeter formulário
            # print("--------> Cheguei aqui no botão de continuar")
            submit_button = self._wait_for_element("//button[@type='submit' and not(@disabled)]")
            submit_button.click()
            ## print("--------> Cliquei no botão")
            #self.browser.ad.sleep_with_jitter(50, 100)
            self.browser.ad.sleep_with_jitter(5, 10)
            
            # Preencher data de nascimento
            if self._fill_birthdate():
                # Aguardar e confirmar código de verificação
                code = self._get_verification_code(account.email)
                if code and self._confirm_verification_code(code):
                    self._save_account(account, "success", self.browser.ad.generate_fingerprint())
                    logger.info("Thread {}: Conta criada com sucesso: {}", self.thread_id, account.username)
                    return True

            self._save_account(account, "failed", self.browser.ad.generate_fingerprint())
            return False

        except Exception as e:
            logger.error("Thread {}: Erro ao criar conta: {}", self.thread_id, e)
            self._save_account(account, "failed", {})
            return False
        finally:
            # Usar o método cleanup em vez de close_browser
            self.cleanup()

    def close_browser(self):
        """Método mantido para compatibilidade - chama cleanup()."""
        self.cleanup()

    def _get_verification_code(self, target_email: str) -> str:
        """Aguarda e busca o código de verificação no Gmail."""
        logger.info("Thread {}: Procurando código de verificação para email: {}", 
                   self.thread_id, target_email)
        
        gmail_reader = GmailReader(self.gmail_username, self.gmail_password)
        if not gmail_reader.connect():
            logger.error("Thread {}: Falha ao conectar ao Gmail.", self.thread_id)
            return None
        
        try:
            max_retries = 5
            timeout = 15

            for attempt in range(max_retries):
                logger.info("Thread {}: Tentativa {}/{} para buscar código...", 
                           self.thread_id, attempt + 1, max_retries)
                
                emails = gmail_reader.read_social_emails(
                    limit=1, 
                    from_email="no-reply@mail.instagram.com", 
                    target_email=target_email
                )
                
                if emails:
                    subject = emails[0]['subject']
                    code_match = re.search(r'\b(\d{6})\b', subject)
                    if code_match:
                        code = code_match.group(1)
                        logger.info("Thread {}: Código de verificação encontrado no assunto: {}", 
                                   self.thread_id, code)
                        gmail_reader.mark_as_read(emails[0]['id'])
                        return code
                    
                    # Fallback para o body
                    body = emails[0]['body']
                    if body:
                        code_match = re.search(r'\b(\d{6})\b', body)
                        if code_match:
                            code = code_match.group(1)
                            logger.info("Thread {}: Código de verificação encontrado no body: {}", 
                                       self.thread_id, code)
                            gmail_reader.mark_as_read(emails[0]['id'])
                            return code
                
                logger.info("Thread {}: Código não encontrado. Aguardando {} segundos...", 
                           self.thread_id, timeout)
                time.sleep(timeout)
            
            logger.warning("Thread {}: Tempo esgotado. Nenhum código encontrado para: {}", 
                          self.thread_id, target_email)
            return None
        finally:
            gmail_reader.disconnect()

    def _wait_for_signup_page(self):
        """Aguarda a página de signup ou verifica redirecionamento."""
        try:
            logger.info("Thread {}: Aguardando página de signup...", self.thread_id)
            self.wait.until(EC.url_contains("accounts/emailsignup"))
            logger.info("Thread {}: Página de signup detectada: {}", 
                       self.thread_id, self.browser.driver.current_url)
        except TimeoutException:
            logger.warning("Thread {}: Redirecionado ou bloqueado. URL atual: {}", 
                          self.thread_id, self.browser.driver.current_url)
            self.browser.driver.save_screenshot(f"debug_screenshot_thread_{self.thread_id}.png")
            raise Exception("Página de signup não carregada.")

    def _wait_for_element(self, xpath: str, timeout: int = 20):
        """Aguarda elemento visível com fallback."""
        try:
            return self.wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
        except TimeoutException:
            logger.warning("Thread {}: Timeout ao aguardar elemento: {}", self.thread_id, xpath)
            raise Exception(f"Elemento {xpath} não encontrado.")

    def _fill_birthdate(self) -> bool:
        """Preenche data de nascimento."""
        try:
            logger.info("Thread {}: Preenchendo data de nascimento...", self.thread_id)
            time.sleep(3)

            month_select = self._wait_for_element("//span[@class='_aav3'][1]//select") # self._wait_for_element("//select[@title='Mês:']")
            month_select.click()
            month_options = month_select.find_elements(By.TAG_NAME, "option")
            random.choice(month_options[1:]).click()

            day_select = self._wait_for_element("//span[@class='_aav3'][2]//select") # self._wait_for_element("//select[@title='Dia:']")
            day_select.click()
            day_options = day_select.find_elements(By.TAG_NAME, "option")
            random.choice(day_options[1:]).click()

            year_select = self._wait_for_element("//span[@class='_aav3'][3]//select") # self._wait_for_element("//select[@title='Ano:']")
            year_select.click()
            year_options = year_select.find_elements(By.TAG_NAME, "option")
            random.choice(year_options[20:40]).click()

            

            # next_button = self._wait_for_element("//button[contains(text(), 'Avançar')]")
            next_button = self._wait_for_element("//button[contains(@class, '_aswr') and contains(@class, '_asws') and not(@disabled)]")
            next_button.click()
            # self.browser.anti.sleep_with_jitter(3, 6)
            self.browser.ad.sleep_with_jitter(5, 10)
            return True
        except Exception as e:
            logger.error("Thread {}: Erro ao preencher data de nascimento: {}", self.thread_id, e)
            return False

    def _confirm_verification_code(self, code: str) -> bool:
        """Confirma código de verificação automaticamente."""
        try:
            logger.info("Thread {}: Inserindo código de verificação: {}", self.thread_id, code)
            code_field = self._wait_for_element("//input[@name='email_confirmation_code']")
            self.browser.human_like_input(code_field, code)

            # confirm_button = self._wait_for_element("//div[@role='button' and contains(text(), 'Avançar')]")
            confirm_button = self._wait_for_element("//div[@role='button'][@tabindex='0']")
            confirm_button.click()
            self.browser.ad.sleep_with_jitter(5, 10)
            return True
        except Exception as e:
            logger.error("Thread {}: Erro ao confirmar código: {}", self.thread_id, e)
            return False

    def _save_account(self, account: AccountData, status: str, fingerprint: Dict):
        accounts_created_file = os.path.join(DATA_DIR, "accounts_created.csv")
        proxy_str = f"{self.proxy.ip}:{self.proxy.port}" if self.proxy else "NO_PROXY"
        logger.info("Detalhes da conta (Thread {}) => Email: {} - username: {} - psw: {} - Status: {} - fingerprint: {}", 
                    self.thread_id, account.email, account.username, account.password, status, proxy_str)

        with self.lock:
            with open(accounts_created_file, "a", newline="", encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    account.email,
                    account.username,
                    account.password,
                    status,
                    time.ctime(),
                    json.dumps(fingerprint),
                    proxy_str,
                    self.thread_id
                ])

    def close_browser_old(self):
        """Fecha o navegador com segurança."""
        try:
            if self.browser and hasattr(self.browser, 'driver') and self.browser.driver:
                self.browser.close()
                logger.info("Thread {}: Browser fechado com sucesso", self.thread_id)
            else:
                logger.warning("Thread {}: Browser já estava fechado ou não inicializado", self.thread_id)
        except Exception as e:
            logger.error("Thread {}: Erro ao fechar browser: {}", self.thread_id, e)


class MultiThreadAccountManager:
    """Gerenciador principal para execução em múltiplas threads."""

    def __init__(self, max_threads: int = 3):
        self.max_threads = max_threads
        self.proxies = []
        self.accounts = []
        self.results = []
        self.setup_logging()

    def setup_logging(self):
        """Configura logging principal."""
        os.makedirs(LOGS_DIR, exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)
        main_log_file = os.path.join(LOGS_DIR, "main.log")
        logger.add(main_log_file, level="INFO", 
                  format="{time} | {level} | {message}")

    def load_proxies(self, file_path: str = None) -> List[ProxyConfig]:
        """Carrega lista de proxies do CSV."""
        if file_path is None:
            file_path = PROXY_CSV_FILE
            
        proxies = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['status'].lower() == 'active':  # Apenas proxies ativos
                        proxies.append(ProxyConfig(
                            ip=row['ip'],
                            port=int(row['port']),
                            username=row['username'],
                            password=row['password'],
                            country=row.get('country', 'Unknown'),
                            city=row.get('city', 'Unknown')
                        ))
            logger.info("Carregados {} proxies ativos", len(proxies))
            self.proxies = proxies
            return proxies
        except Exception as e:
            logger.error("Erro ao carregar proxies: {}", e)
            return []

    def load_accounts(self, file_path: str = None) -> List[AccountData]:
        """Carrega lista de contas do CSV."""
        if file_path is None:
            file_path = ACCOUNTS_CSV_FILE
            
        accounts = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    accounts.append(AccountData(
                        email=row['email'],
                        full_name=row['full_name'],
                        username=row['username'],
                        password=row['password']
                    ))
            logger.info("Carregadas {} contas para criação", len(accounts))
            self.accounts = accounts
            return accounts
        except Exception as e:
            logger.error("Erro ao carregar contas: {}", e)
            return []

    def create_accounts_parallel(self) -> Dict:
        """Executa criação de contas em paralelo."""
        def _fmt_proxy(p):
            return f"{p.ip}:{p.port}" if p else "SEM PROXY"
    
        # DEPOIS
        if not self.accounts:
            logger.error("Nenhuma conta carregada")
            return {"success": 0, "failed": 0, "results": []}

        # Limita threads pelo número EXATO especificado pelo usuário
        # mas não pode ser maior que o número de contas disponíveis
        actual_threads = min(self.max_threads, len(self.accounts))
        logger.info("Execução configurada para {} threads (máximo: {})", actual_threads, self.max_threads)
        logger.info("Processando {} contas com {} proxies disponíveis", len(self.accounts), len(self.proxies))

        # Prepara arquivo de resultados - ANEXA em vez de sobrescrever
        accounts_created_file = os.path.join(DATA_DIR, "accounts_created.csv")
        
        # Verifica se o arquivo já existe para decidir se adiciona cabeçalho
        file_exists = os.path.exists(accounts_created_file)
        
        if not file_exists:
            # Cria arquivo com cabeçalho se não existir
            with open(accounts_created_file, "w", newline="", encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['email', 'username', 'password', 'status', 'created_at', 
                               'fingerprint', 'proxy_used', 'thread_id'])
            logger.info("Arquivo de resultados criado: {}", accounts_created_file)
        else:
            logger.info("Anexando resultados ao arquivo existente: {}", accounts_created_file)

        results = {"success": 0, "failed": 0, "results": []}
        
        with ThreadPoolExecutor(max_workers=actual_threads) as executor:
            # Mapeia APENAS as contas que cabem no número de threads especificado
            future_to_data = {}
            
            # Processa apenas o número de contas igual ao número de threads
            accounts_to_process = self.accounts[:actual_threads]
            logger.info("Processando {} contas em {} threads", len(accounts_to_process), actual_threads)
            
            shuffled_proxies = self.proxies.copy() 
            random.shuffle(shuffled_proxies)
            
            for i, account in enumerate(accounts_to_process):
                # Usa proxy de forma circular se há mais threads que proxies
                if USE_PROXIES and self.proxies:
                    # Usa proxy de forma circular
                    # proxy = self.proxies[i % len(self.proxies)]

                    # Usa de forma aleatoria
                    proxy = shuffled_proxies[i]                    

                else:
                    proxy = None

                thread_id = i + 1
                
                logger.info("Iniciando Thread {}: {} -> Proxy {}", thread_id, account.username, _fmt_proxy(proxy))

                
                creator = ThreadSafeAccountCreator(thread_id, proxy)
                future = executor.submit(creator.create_account, account)
                future_to_data[future] = {
                    'thread_id': thread_id,
                    'account': account,
                    'proxy': proxy
                }

            # Processa resultados conforme completam
            for future in as_completed(future_to_data):
                data = future_to_data[future]
                try:
                    success = future.result()
                    if success:
                        results["success"] += 1
                        logger.info("✅ Thread {}: Conta {} criada com sucesso", 
                                   data['thread_id'], data['account'].username)
                    else:
                        results["failed"] += 1
                        logger.error("❌ Thread {}: Falha ao criar conta {}", 
                                    data['thread_id'], data['account'].username)
                    
                    results["results"].append({
                        'thread_id': data['thread_id'],
                        'account': data['account'].username,
                        'proxy': (f"{data['proxy'].ip}:{data['proxy'].port}" if data['proxy'] else "NO_PROXY"),
                        'success': success
                    })
                    
                except Exception as e:
                    results["failed"] += 1
                    logger.error("❌ Thread {}: Exceção ao processar conta {}: {}", 
                                data['thread_id'], data['account'].username, e)

        return results

    def run(self, proxies_file: str = None, accounts_file: str = None):
        """Execução principal do gerenciador."""
        logger.info("🚀 Iniciando MultiThreadAccountManager com {} threads máximas", self.max_threads)
        
        # Usar caminhos padrão se não especificados
        if proxies_file is None:
            proxies_file = PROXY_CSV_FILE
        if accounts_file is None:
            accounts_file = ACCOUNTS_CSV_FILE
        
        # Carrega dados
        self.load_proxies(proxies_file)
        self.load_accounts(accounts_file)
        
        if not self.proxies:
            logger.error("❌ Nenhum proxy ativo encontrado")
            return
        
        from src.account_creator_multithreaded import USE_PROXIES  # se necessário (ou já está no escopo)
        if USE_PROXIES and not self.proxies:
            logger.error("❌ Nenhum proxy ativo encontrado (USE_PROXIES=True)")
            return
            
        if not self.accounts:
            logger.error("❌ Nenhuma conta encontrada")
            return

        # Executa criação paralela
        start_time = time.time()
        results = self.create_accounts_parallel()
        execution_time = time.time() - start_time

        # Log de resultados finais
        logger.info("📊 RESULTADOS FINAIS:")
        logger.info("✅ Contas criadas com sucesso: {}", results["success"])
        logger.info("❌ Falhas: {}", results["failed"])
        logger.info("⏱️ Tempo total de execução: {:.2f} segundos", execution_time)
        logger.info("📁 Resultados salvos em: {}", os.path.join(DATA_DIR, "accounts_created.csv"))
        
        return results


if __name__ == "__main__":
    # Configurações
    MAX_THREADS = int(input("Quantas threads deseja usar? (padrão: 3): ") or "3")
    
    print(f"🔧 Configurando execução com {MAX_THREADS} threads...")
    
    # Cria e executa o gerenciador
    manager = MultiThreadAccountManager(max_threads=MAX_THREADS)
    
    try:
        results = manager.run()
        print(f"\n🎉 Execução concluída!")
        print(f"✅ Sucessos: {results['success']}")
        print(f"❌ Falhas: {results['failed']}")
        
    except KeyboardInterrupt:
        print("\n🛑 Execução interrompida pelo usuário")
    except Exception as e:
        print(f"\n💥 Erro durante execução: {e}")
        logger.error("Erro durante execução: {}", e)