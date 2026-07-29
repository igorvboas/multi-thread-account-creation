import json
import random
import time
import os
import zipfile
from typing import Dict, Optional

import yaml
from loguru import logger
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.proxy import Proxy, ProxyType
import undetected_chromedriver as uc
from fake_useragent import UserAgent

import logging


def detect_chrome_major() -> Optional[int]:
    """Retorna a major version do Chrome instalado, ou None se não detectar.

    O undetected_chromedriver precisa de um driver da mesma major do browser;
    sem isso ele baixa o mais recente e a sessão falha com 'session not created'.
    """
    import re
    import subprocess

    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "google-chrome",
        "chromium",
        "chrome",
    ]

    for binary in candidates:
        try:
            output = subprocess.run(
                [binary, "--version"], capture_output=True, text=True, timeout=10
            ).stdout
        except (OSError, subprocess.SubprocessError):
            continue

        match = re.search(r"(\d+)\.\d+\.\d+", output)
        if match:
            major = int(match.group(1))
            logger.info("Chrome detectado: major {} ({})", major, output.strip())
            return major

    logger.warning("Não foi possível detectar a versão do Chrome; usando o driver mais recente")
    return None


class AntiDetection:
    """Classe para estratégias anti-detecção em automações web."""

    def __init__(self, config_path: str = "config/config.yaml", proxies_path: str = "config/proxies.csv"):
        self.config = self._load_config(config_path)
        self.proxies = self._load_proxies(proxies_path)
        self.user_agents = self.config.get("browser", {}).get("user_agents", [])
        self.headless = self.config.get("browser", {}).get("headless", False)
        self.use_proxies = self.config.get("proxies", {}).get("use_proxies", True)
        self.logger = logger.bind()  # Adiciona logger específico para a instância
        # logger.info(f"AntiDetection inicializado com {len(self.proxies)} proxies e {len(self.user_agents)} user agents.")
        logger.info(f"AntiDetection inicializado com {len(self.proxies)}")

    def _load_config(self, path: str) -> Dict:
        """Carrega configurações de YAML."""
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error("Erro ao carregar config: {}", e)
            return {}

    def _load_proxies_json(self, path: str) -> list[Dict]:
        """Carrega lista de proxies de JSON."""
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Erro ao carregar proxies: {}", e)
            return []
        
    def _load_proxies(self, path: str) -> list[Dict]:
        """Carrega lista de proxies do arquivo CSV."""
        try:
            import csv
            proxies = []
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Verificar se o proxy está ativo
                    if row.get('status', '').lower() == 'active':
                        try:
                            proxy_data = {
                                'ip': row['ip'].strip(),
                                'port': int(row['port']),
                                'username': row['username'].strip(),
                                'password': row['password'].strip(),
                                'country': row.get('country', 'Unknown').strip(),
                                'country_code': row.get('country_code', 'XX').strip(),
                                'city': row.get('city', 'Unknown').strip(),
                                'last_checked': row.get('last_checked', '').strip()
                            }
                            proxies.append(proxy_data)
                        except (ValueError, KeyError) as e:
                            logger.warning("Proxy inválido ignorado - linha {}: {}", reader.line_num, e)
                            continue
                            
            logger.info("Carregados {} proxies ativos do arquivo {}", len(proxies), path)
            return proxies
            
        except FileNotFoundError:
            logger.error("Arquivo de proxies não encontrado: {}", path)
            return []
        except Exception as e:
            logger.error("Erro ao carregar proxies do CSV: {}", e)
            return []
    

    def apply_proxy(self, proxy: Dict):
        """Aplica o proxy ao ambiente de navegação."""
        self.logger.info("Aplicando proxy: {}:{}", proxy["ip"], proxy["port"])
        # Lógica para aplicar proxy (já existe em create_proxy_extension)
        plugin_path = self.create_proxy_extension(proxy)
        options = self.configure_browser_options()
        options.add_extension(plugin_path)
        # Se necessário, re-inicializar o driver com o proxy

    def get_random_delay(self, min_delay: Optional[int] = None, max_delay: Optional[int] = None) -> float:
        """Gera delay randômico entre min e max (de config se não fornecido)."""
        min_d = min_delay or self.config.get("delays", {}).get("min_action", 5)
        max_d = max_delay or self.config.get("delays", {}).get("max_action", 15)
        delay = random.uniform(min_d, max_d)
        logger.debug("Delay gerado: {} segundos.", delay)
        return delay

    def sleep_with_jitter(self, min_delay: Optional[int] = None, max_delay: Optional[int] = None):
        """Aplica sleep com delay randômico."""
        time.sleep(self.get_random_delay(min_delay, max_delay))

    def get_random_user_agent_old(self) -> str:
        """Seleciona user agent randômico da lista ou gera com fake_useragent."""
        if not self.user_agents:
            ua = UserAgent()
            return ua.random
        ua = random.choice(self.user_agents)
        logger.debug("User agent selecionado: {}", ua)
        return ua
    
    def get_random_user_agent(self) -> str:
        """Seleciona user agent dinâmico usando fake_useragent."""
        ua = UserAgent(browsers=['chrome', 'firefox', 'safari', 'edge'], os=['windows', 'macos', 'linux', 'android', 'ios'])
        user_agent = ua.random
        logger.debug("User agent selecionado: {}", user_agent)
        return user_agent

    def get_random_proxy(self) -> Optional[Dict]:
        """Seleciona proxy randômico da lista."""
        if not self.use_proxies or not self.proxies:
            logger.warning("Proxies desativados ou lista vazia.")
            return None
        proxy = random.choice(self.proxies)
        logger.debug("Proxy selecionado: {}:{}", proxy["ip"], proxy["port"])
        return proxy

    def create_proxy_extension(self, proxy: Dict) -> str:
        """Cria extensão de proxy autenticado."""
        user_pass = f"{proxy['username']}:{proxy['password']}"
        ip_port = f"{proxy['ip']}:{proxy['port']}"
        proxy_str = f"{user_pass}@{ip_port}"

        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "<all_urls>",
                "webRequest",
                "webRequestBlocking"
            ],
            "background": {
                "scripts": ["background.js"]
            }
        }
        """
        background_js = f"""
        var config = {{
            mode: "fixed_servers",
            rules: {{
                singleProxy: {{
                    scheme: "http",
                    host: "{proxy['ip']}",
                    port: parseInt({proxy['port']})
                }},
                bypassList: ["localhost"]
            }}
        }};
        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function(){{}});
        chrome.webRequest.onAuthRequired.addListener(
            function(details) {{
                return {{
                    authCredentials: {{
                        username: "{proxy['username']}",
                        password: "{proxy['password']}"
                    }}
                }};
            }},
            {{urls: ["<all_urls>"]}},
            ['blocking']
        );
        """

        plugin_path = "proxy_auth_plugin.zip"
        with zipfile.ZipFile(plugin_path, "w") as zp:
            zp.writestr("manifest.json", manifest_json)
            zp.writestr("background.js", background_js)
        return plugin_path

    def generate_fingerprint_old(self) -> Dict:
        """Gera um fingerprint desktop simplificado com variações."""
        return {
            "user_agent": self.get_random_user_agent(),
            "screen_width": random.randint(1280, 1920),
            "screen_height": random.randint(720, 1080),
            "device_pixel_ratio": round(random.uniform(1.0, 2.0), 1),
            "timezone": random.choice(["America/Sao_Paulo", "America/New_York", "Europe/Berlin", "Europe/Paris"]),
            "language": random.choice(["pt-BR,pt;q=0.9,en;q=0.8", "en-US,en;q=0.9", "de-DE,de;q=0.9,en;q=0.8", "fr-FR,fr;q=0.9,en;q=0.8"]),
            "platform": random.choice(["Windows NT 10.0", "Macintosh; Intel Mac OS X 10_15_7"])
        }
    
    def generate_fingerprint(self, proxy: Optional[Dict] = None) -> Dict:
        """Gera um fingerprint alinhado com o proxy e com suporte a dispositivos móveis."""
        # Mapeamento de países para timezones e languages
        country_timezones = {
            "Brazil": "America/Sao_Paulo",
            "United States of America": "America/New_York",
            "Germany": "Europe/Berlin",
            "France": "Europe/Paris",
            "Thailand": "Asia/Bangkok",
            "Canada": "America/Toronto",
            "United Kingdom": "Europe/London",
            "Italy": "Europe/Rome",
            "Unknown": "America/New_York"
        }
        country_languages = {
            "Brazil": "pt-BR,pt;q=0.9,en;q=0.8",
            "United States of America": "en-US,en;q=0.9",
            "Germany": "de-DE,de;q=0.9,en;q=0.8",
            "France": "fr-FR,fr;q=0.9,en;q=0.8",
            "Thailand": "th-TH,th;q=0.9,en;q=0.8",
            "Canada": "en-CA,en;q=0.9,fr-CA;q=0.8",
            "United Kingdom": "en-GB,en;q=0.9",
            "Italy": "it-IT,it;q=0.9,en;q=0.8",
            "Unknown": "en-US,en;q=0.9"
        }
        
        # Determina o país do proxy ou usa fallback
        country = proxy.get("country", "Unknown") if proxy else "Unknown"
        
        # Determina se é dispositivo móvel (50% de chance para simular Instagram mobile)
        is_mobile = random.choice([True, False])
        
        # Escolhe plataforma baseada no tipo de dispositivo
        if is_mobile:
            platform = random.choice([
                "iPhone; CPU iPhone OS 18_0 like Mac OS X",
                "Linux; Android 14"
            ])
            screen_width = random.randint(360, 414)  # Resoluções típicas de smartphones
            screen_height = random.randint(640, 896)
            device_pixel_ratio = round(random.uniform(2.0, 3.5), 1)  # Pixel ratio de dispositivos móveis
        else:
            platform = random.choice([
                "Windows NT 10.0; Win64; x64",
                "Macintosh; Intel Mac OS X 14_6_1"
            ])
            screen_width = random.randint(1280, 1920)
            screen_height = random.randint(720, 1080)
            device_pixel_ratio = round(random.uniform(1.0, 2.0), 1)
        
        return {
            "user_agent": self.get_random_user_agent(),
            "screen_width": screen_width,
            "screen_height": screen_height,
            "device_pixel_ratio": device_pixel_ratio,
            "timezone": country_timezones.get(country, "America/New_York"),
            "language": country_languages.get(country, "en-US,en;q=0.9"),
            "platform": platform,
            "hardware_concurrency": random.choice([2, 4, 8, 16]),  # Simula núcleos de CPU
            "device_memory": random.choice([4, 8, 16, 32])  # Memória em GB
        }

    def configure_browser_options_old(self, options: Optional[ChromeOptions] = None, fingerprint: Optional[Dict] = None, proxy: Optional[Dict] = None, headless_override: Optional[bool] = None) -> ChromeOptions:
    # def configure_browser_options(self, options: Optional[ChromeOptions] = None, fingerprint: Optional[Dict] = None) -> ChromeOptions:
        """Configura opções do Selenium para anti-detecção com fingerprint opcional."""
        if options is None:
            options = ChromeOptions()
        fp = fingerprint or self.generate_fingerprint()
        options.add_argument(f'--user-agent={fp["user_agent"]}')
        options.add_argument(f'--window-size={fp["screen_width"]},{fp["screen_height"]}')
        options.add_argument(f'--device-scale-factor={fp["device_pixel_ratio"]}')

        if headless_override is not None:
            local_headless = headless_override
        else:
            local_headless = self.headless

        # Adicionar opções específicas para modo não-headless
        # if not self.headless:
        if not local_headless:
            options.add_argument('--start-maximized')
            options.add_argument('--disable-dev-tools')

        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-background-networking')
        options.add_argument('--disable-default-apps')
        options.add_argument('--no-first-run')
        options.add_argument('--disable-sync')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=VizDisplayCompositor')
        options.add_argument('--disable-logging')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--disable-translate')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-field-trial-config')
        options.add_argument('--disable-ipc-flooding-protection')
        options.add_argument('--memory-pressure-off')
        options.add_argument('--max_old_space_size=4096')
        options.add_argument('--force-device-scale-factor=1')
        options.add_argument('--disable-crash-reporter')
        options.add_argument('--disable-hang-monitor')
        options.add_argument('--disable-client-side-phishing-detection')
        options.add_argument('--disable-component-update')
        options.add_argument('--disable-domain-reliability')
        options.add_argument('--disable-features=TranslateUI')

        # Configurar timezone via CDP (se suportado)
        if fingerprint:
            options.add_argument(f'--lang={fp["language"].split(",")[0]}')
            # self.driver.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": fp["timezone"]})


        # Prefs
        prefs = {
            "profile.default_content_setting_values": {
                "notifications": 2,
                "geolocation": 2,
                "media_stream": 2,
            },
            "profile.managed_default_content_settings": {
                "images": 2
            },
            "intl.accept_languages": fp["language"]
        }
        options.add_experimental_option("prefs", prefs)

        # Proxy
        effective_proxy = None
        if proxy:
            # Proxy forçado vindo da thread
            effective_proxy = proxy
        elif self.use_proxies:
            # Fallback: usa o random do proxies.json (comportamento antigo)
            effective_proxy = self.get_random_proxy()

        if effective_proxy:
            plugin_path = self.create_proxy_extension(effective_proxy)  # suporta user/pass
            options.add_extension(plugin_path)


        # if self.headless:
        if local_headless:
            options.add_argument("--headless=new")

        return options
    
    def configure_browser_options(self, options: Optional[ChromeOptions] = None, fingerprint: Optional[Dict] = None, proxy: Optional[Dict] = None, headless_override: Optional[bool] = None) -> ChromeOptions:
        """Configura opções do Selenium para anti-detecção com fingerprint opcional."""
        if options is None:
            options = ChromeOptions()
        fp = fingerprint or self.generate_fingerprint(proxy=proxy)
        options.add_argument(f'--user-agent={fp["user_agent"]}')
        options.add_argument(f'--window-size={fp["screen_width"]},{fp["screen_height"]}')
        options.add_argument(f'--device-scale-factor={fp["device_pixel_ratio"]}')

        if headless_override is not None:
            local_headless = headless_override
        else:
            local_headless = self.headless

        # Adicionar opções específicas para modo não-headless
        if not local_headless:
            options.add_argument('--start-maximized')
            options.add_argument('--disable-dev-tools')

        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-background-networking')
        options.add_argument('--disable-default-apps')
        options.add_argument('--no-first-run')
        options.add_argument('--disable-sync')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=VizDisplayCompositor')
        options.add_argument('--disable-logging')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--disable-translate')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-field-trial-config')
        options.add_argument('--disable-ipc-flooding-protection')
        options.add_argument('--memory-pressure-off')
        options.add_argument('--max_old_space_size=4096')
        options.add_argument('--force-device-scale-factor=1')
        options.add_argument('--disable-crash-reporter')
        options.add_argument('--disable-hang-monitor')
        options.add_argument('--disable-client-side-phishing-detection')
        options.add_argument('--disable-component-update')
        options.add_argument('--disable-domain-reliability')
        options.add_argument('--disable-features=TranslateUI')
        
        # Adicionar hardwareConcurrency e deviceMemory
        options.add_argument(f'--hardware-concurrency={fp["hardware_concurrency"]}')
        options.add_argument(f'--device-memory={fp["device_memory"]}')

        # Configurar language
        options.add_argument(f'--lang={fp["language"].split(",")[0]}')

        # Prefs
        prefs = {
            "profile.default_content_setting_values": {
                "notifications": 2,
                "geolocation": 2,
                "media_stream": 2,
            },
            "profile.managed_default_content_settings": {
                "images": 2
            },
            "intl.accept_languages": fp["language"]
        }
        options.add_experimental_option("prefs", prefs)

        # Proxy
        effective_proxy = None
        if proxy:
            effective_proxy = proxy
        elif self.use_proxies:
            effective_proxy = self.get_random_proxy()

        if effective_proxy:
            plugin_path = self.create_proxy_extension(effective_proxy)
            options.add_extension(plugin_path)

        if local_headless:
            options.add_argument("--headless=new")

        return options
    
    def get_undetected_driver(self, fingerprint: Optional[Dict] = None, proxy: Optional[Dict] = None, headless: Optional[bool] = None):
        """
        Cria driver undetected com fingerprinting e tratamento robusto de erros.
        """
        try:
            logger.info("Iniciando criação do driver undetected...")
            
            # Gerar fingerprint se não fornecido
            if fingerprint is None:
                fingerprint = self.generate_fingerprint(proxy=proxy)
                logger.debug("Fingerprint gerado: {}", fingerprint)
            
            # Configurar opções do browser
            options = self.configure_browser_options(
                fingerprint=fingerprint,
                proxy=proxy,
                headless_override=headless
            )
            
            # Opções adicionais para estabilidade
            options.add_argument('--no-first-run')
            options.add_argument('--no-default-browser-check')
            options.add_argument('--disable-default-apps')
            options.add_argument('--disable-crash-reporter')
            options.add_argument('--disable-hang-monitor')
            
            logger.info("Opções configuradas, criando driver Chrome...")
            
            # Criar driver casando com a versão do Chrome instalado.
            # version_main=None faria o uc baixar o driver mais recente, que
            # quebra sempre que o Chrome local está uma major atrás.
            driver = uc.Chrome(options=options, version_main=detect_chrome_major())
            
            if driver is None:
                raise Exception("uc.Chrome retornou None")
            
            logger.info("Driver criado com sucesso, configurando timeouts...")
            
            # Configurar timeouts
            driver.implicitly_wait(15)
            driver.set_page_load_timeout(90)
            driver.set_script_timeout(90)
            
            # Remover __del__ problemático (pode causar erros no fechamento)
            driver.__del__ = lambda: None
            
            # Aplicar fingerprint via CDP se fornecido
            if fingerprint:
                try:
                    logger.debug("Aplicando configurações CDP...")
                    
                    # Configurar timezone
                    driver.execute_cdp_cmd("Emulation.setTimezoneOverride", {
                        "timezoneId": fingerprint["timezone"]
                    })
                    
                    # Script anti-detecção avançado
                    anti_detection_script = """
                        // Randomizar canvas para evitar fingerprinting
                        const originalGetContext = HTMLCanvasElement.prototype.getContext;
                        HTMLCanvasElement.prototype.getContext = function(contextType, attributes) {
                            const context = originalGetContext.call(this, contextType, attributes);
                            if (contextType === '2d' || contextType === 'webgl') {
                                const shift = Math.random() * 0.0001;
                                context.fillStyle = `rgba(${Math.floor(Math.random() * 256)}, ${Math.floor(Math.random() * 256)}, ${Math.floor(Math.random() * 256)}, ${1 + shift})`;
                            }
                            return context;
                        };
                        
                        // Bloquear acesso a navigator.webdriver
                        Object.defineProperty(navigator, 'webdriver', { 
                            get: () => undefined 
                        });
                        
                        // Simular hardwareConcurrency
                        Object.defineProperty(navigator, 'hardwareConcurrency', { 
                            get: () => %d 
                        });
                        
                        // Simular deviceMemory
                        Object.defineProperty(navigator, 'deviceMemory', { 
                            get: () => %d 
                        });
                        
                        // Mascarar outras propriedades de detecção
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => [1, 2, 3, 4, 5]
                        });
                        
                        // Remover rastros de automação
                        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
                        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
                        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
                    """ % (
                        fingerprint.get("hardware_concurrency", 4), 
                        fingerprint.get("device_memory", 8)
                    )
                    
                    # Aplicar script
                    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                        "source": anti_detection_script
                    })
                    
                    logger.info("Configurações CDP aplicadas com sucesso")
                    
                except Exception as cdp_error:
                    logger.warning("Falha ao aplicar configurações via CDP: {}", cdp_error)
                    # Não falha completamente, apenas avisa
            
            # Armazenar referência
            self.driver = driver
            
            logger.info("Navegador undetected configurado com sucesso. Fingerprint: {}", 
                    fingerprint.get("user_agent", "N/A")[:50] + "...")
            
            return driver
            
        except Exception as e:
            logger.error("Erro crítico ao inicializar undetected_chromedriver: {}", e)
            # Limpar referência se falhou
            self.driver = None
            raise Exception(f"Falha ao inicializar driver: {str(e)}")
            
        except KeyboardInterrupt:
            logger.info("Inicialização do driver cancelada pelo usuário")
            raise

    
    # Funções adicionais para mimetizar comportamento humano
    def human_like_scroll(self, driver):
        """Simula scroll humano."""
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        self.sleep_with_jitter(1, 3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        self.sleep_with_jitter(1, 3)

    def human_like_type(self, element, text: str):
        """Simula digitação humana com delays."""
        for char in text:
            element.send_keys(char)
            self.sleep_with_jitter(0.1, 0.3)