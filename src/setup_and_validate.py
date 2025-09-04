#!/usr/bin/env python3
"""
Script utilitário para validar e preparar arquivos para automação Instagram.

Este script:
1. Verifica a estrutura dos arquivos CSV
2. Valida proxies ativos
3. Testa conectividade com Gmail
4. Prepara ambiente para execução

Uso:
    python setup_and_validate.py
    python setup_and_validate.py --test-proxies
    python setup_and_validate.py --test-gmail
"""

import argparse
import csv
import os
import sys
import time
from typing import List, Dict, Tuple
import concurrent.futures
import requests
from colorama import Fore, Style, init
from loguru import logger
from dotenv import load_dotenv
import imaplib
from gmail_reader import GmailReader

init()
load_dotenv()

# Variáveis globais para caminhos dos arquivos
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROXY_CSV_FILE = os.path.join(SCRIPT_DIR, 'proxies.csv')
ACCOUNTS_CSV_FILE = os.path.join(SCRIPT_DIR, 'accounts_data.csv')
DATA_DIR = os.path.join(SCRIPT_DIR, 'data')
LOGS_DIR = os.path.join(SCRIPT_DIR, 'logs')

# Criar diretórios se não existirem
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

class FileValidator:
    """Valida estrutura e conteúdo dos arquivos CSV."""
    
    REQUIRED_PROXY_COLUMNS = ['ip', 'port', 'username', 'password', 'status']
    REQUIRED_ACCOUNT_COLUMNS = ['email', 'full_name', 'username', 'password']
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate_csv_structure(self, filepath: str, required_columns: List[str]) -> bool:
        """Valida estrutura do arquivo CSV."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                columns = reader.fieldnames or []
                
                missing_columns = [col for col in required_columns if col not in columns]
                if missing_columns:
                    self.errors.append(f"❌ {filepath}: Colunas ausentes: {missing_columns}")
                    return False
                
                # Conta linhas
                rows = list(reader)
                if len(rows) == 0:
                    self.errors.append(f"❌ {filepath}: Arquivo vazio")
                    return False
                
                print(f"✅ {filepath}: {len(rows)} linhas, colunas OK")
                return True
                
        except FileNotFoundError:
            self.errors.append(f"❌ Arquivo não encontrado: {filepath}")
            return False
        except Exception as e:
            self.errors.append(f"❌ Erro ao ler {filepath}: {e}")
            return False
    
    def validate_proxies_file(self, filepath: str = None) -> Dict:
        """Valida arquivo de proxies e retorna estatísticas."""
        if filepath is None:
            filepath = PROXY_CSV_FILE
            
        print(f"\n{Fore.BLUE}🔍 Validando arquivo de proxies: {filepath}{Style.RESET_ALL}")
        
        if not self.validate_csv_structure(filepath, self.REQUIRED_PROXY_COLUMNS):
            return {"valid": False, "total": 0, "active": 0}
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                proxies = list(reader)
                
                total_proxies = len(proxies)
                
                # Conta proxies por status
                status_counts = {}
                for proxy in proxies:
                    status = proxy.get('status', '').lower().strip()
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                active_proxies = status_counts.get('active', 0)
                
                print(f"📊 Total de proxies: {total_proxies}")
                print(f"✅ Proxies ativos: {active_proxies}")
                
                # Mostra breakdown de status
                print(f"📋 Status encontrados:")
                for status, count in status_counts.items():
                    status_display = status if status else "(vazio)"
                    print(f"  • {status_display}: {count}")
                
                if active_proxies == 0:
                    print(f"{Fore.YELLOW}⚠️  IMPORTANTE: Nenhum proxy com status 'active' encontrado!{Style.RESET_ALL}")
                    print(f"💡 Para os proxies serem testados, a coluna 'status' deve conter 'active' (minúsculo)")
                
                # Valida formato IP:porta
                invalid_proxies = []
                for i, proxy in enumerate(proxies, 1):
                    try:
                        ip = proxy.get('ip', '').strip()
                        port = int(proxy.get('port', 0))
                        if not ip or port <= 0 or port > 65535:
                            invalid_proxies.append(f"Linha {i}")
                    except ValueError:
                        invalid_proxies.append(f"Linha {i} (porta inválida)")
                
                if invalid_proxies:
                    self.warnings.append(f"⚠️  Proxies com formato inválido: {invalid_proxies[:5]}")
                
                return {
                    "valid": True,
                    "total": total_proxies,
                    "active": active_proxies,
                    "invalid": len(invalid_proxies),
                    "status_breakdown": status_counts
                }
                
        except Exception as e:
            self.errors.append(f"❌ Erro ao processar proxies: {e}")
            return {"valid": False, "total": 0, "active": 0}
    
    def validate_accounts_file(self, filepath: str = None) -> Dict:
        """Valida arquivo de contas e retorna estatísticas."""
        if filepath is None:
            filepath = ACCOUNTS_CSV_FILE
            
        print(f"\n{Fore.BLUE}🔍 Validando arquivo de contas: {filepath}{Style.RESET_ALL}")
        
        if not self.validate_csv_structure(filepath, self.REQUIRED_ACCOUNT_COLUMNS):
            return {"valid": False, "total": 0}
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                accounts = list(reader)
                
                total_accounts = len(accounts)
                print(f"📊 Total de contas: {total_accounts}")
                
                # Validações básicas
                invalid_emails = []
                duplicate_usernames = set()
                duplicate_emails = set()
                
                usernames_seen = set()
                emails_seen = set()
                
                for i, account in enumerate(accounts, 1):
                    email = account.get('email', '').strip()
                    username = account.get('username', '').strip()
                    
                    # Valida email
                    if '@' not in email or '.' not in email:
                        invalid_emails.append(f"Linha {i}")
                    
                    # Verifica duplicatas
                    if username in usernames_seen:
                        duplicate_usernames.add(username)
                    else:
                        usernames_seen.add(username)
                    
                    if email in emails_seen:
                        duplicate_emails.add(email)
                    else:
                        emails_seen.add(email)
                
                # Reporta problemas
                if invalid_emails:
                    self.warnings.append(f"⚠️  Emails inválidos: {invalid_emails[:5]}")
                
                if duplicate_usernames:
                    self.warnings.append(f"⚠️  Usernames duplicados: {list(duplicate_usernames)[:3]}")
                
                if duplicate_emails:
                    self.warnings.append(f"⚠️  Emails duplicados: {list(duplicate_emails)[:3]}")
                
                return {
                    "valid": True,
                    "total": total_accounts,
                    "invalid_emails": len(invalid_emails),
                    "duplicate_usernames": len(duplicate_usernames),
                    "duplicate_emails": len(duplicate_emails)
                }
                
        except Exception as e:
            self.errors.append(f"❌ Erro ao processar contas: {e}")
            return {"valid": False, "total": 0}


class ProxyTester:
    """Testa conectividade e velocidade dos proxies usando método robusto."""
    
    def __init__(self):
        self.timeout = 15  # Timeout maior como no seu código
        self.test_urls = [
            'http://httpbin.org/ip',
            'https://httpbin.org/ip',
            'http://icanhazip.com',
            'https://api.ipify.org?format=json'
        ]
    
    def test_proxy(self, proxy: Dict) -> Tuple[bool, float, str]:
        """Testa um proxy individual usando múltiplas URLs."""
        start_time = time.time()
        
        try:
            # Monta URL do proxy com autenticação
            proxy_url = f"http://{proxy['username']}:{proxy['password']}@{proxy['ip']}:{proxy['port']}"
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            
            # Testa múltiplas URLs até uma funcionar
            for test_url in self.test_urls:
                try:
                    response = requests.get(
                        test_url,
                        proxies=proxies,
                        timeout=self.timeout,
                        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                    )
                    
                    response_time = time.time() - start_time
                    
                    if response.status_code == 200:
                        # Extrai IP real da resposta
                        try:
                            if 'json' in response.headers.get('content-type', '').lower():
                                data = response.json()
                                real_ip = data.get('origin') or data.get('ip')
                            else:
                                real_ip = response.text.strip()
                        except:
                            real_ip = "IP não identificado"
                        
                        return True, response_time, f"OK - IP: {real_ip}"
                    
                except requests.exceptions.Timeout:
                    continue  # Tenta próxima URL
                except requests.exceptions.ConnectionError:
                    continue  # Tenta próxima URL
                except requests.exceptions.ProxyError:
                    continue  # Tenta próxima URL
                except Exception:
                    continue  # Tenta próxima URL
            
            # Se chegou aqui, nenhuma URL funcionou
            return False, time.time() - start_time, "Todas as URLs falharam"
                
        except Exception as e:
            return False, time.time() - start_time, f"Erro geral: {str(e)}"
    
    def test_proxies_batch(self, proxies_file: str = None, max_workers: int = 5) -> Dict:
        """Testa múltiplos proxies em paralelo com método robusto."""
        if proxies_file is None:
            proxies_file = PROXY_CSV_FILE
            
        print(f"\n{Fore.BLUE}🧪 Testando proxies em lote (método robusto)...{Style.RESET_ALL}")
        
        try:
            with open(proxies_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                all_proxies = list(reader)
                
                # Filtra proxies ativos
                active_proxies = [p for p in all_proxies if p.get('status', '').lower() == 'active']
                
                print(f"📊 Total de proxies no arquivo: {len(all_proxies)}")
                print(f"✅ Proxies ativos para testar: {len(active_proxies)}")
            
            if not active_proxies:
                print(f"❌ Nenhum proxy ativo encontrado em {proxies_file}")
                print(f"💡 Dica: Verifique se a coluna 'status' contém 'active' (minúsculo)")
                return {"tested": 0, "working": 0, "failed": 0}
            
            print(f"⚙️ Configurações: Timeout={self.timeout}s, Workers={max_workers}")
            print(f"🌐 URLs de teste: {', '.join(self.test_urls)}")
            print("-" * 70)
            
            results = {"tested": 0, "working": 0, "failed": 0, "details": []}
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_proxy = {executor.submit(self.test_proxy, proxy): proxy for proxy in active_proxies}
                
                for i, future in enumerate(concurrent.futures.as_completed(future_to_proxy), 1):
                    proxy = future_to_proxy[future]
                    
                    try:
                        is_working, response_time, status = future.result()
                        results["tested"] += 1
                        
                        if is_working:
                            results["working"] += 1
                            print(f"✅ {proxy['ip']}:{proxy['port']} - {response_time:.2f}s - {status}")
                        else:
                            results["failed"] += 1
                            print(f"❌ {proxy['ip']}:{proxy['port']} - {status}")
                        
                        results["details"].append({
                            "proxy": f"{proxy['ip']}:{proxy['port']}",
                            "working": is_working,
                            "response_time": response_time,
                            "status": status
                        })
                        
                        # Progress indicator a cada 3 proxies testados
                        if i % 3 == 0:
                            print(f"📊 Progresso: {i}/{len(active_proxies)} proxies testados")
                            
                    except Exception as e:
                        results["failed"] += 1
                        print(f"💥 {proxy['ip']}:{proxy['port']} - Erro no teste: {e}")
            
            print(f"\n{Fore.GREEN}📊 RESULTADO DOS TESTES:{Style.RESET_ALL}")
            print("=" * 50)
            print(f"✅ Proxies funcionais: {results['working']}")
            print(f"❌ Proxies com falha: {results['failed']}")
            success_rate = (results['working'] / results['tested'] * 100) if results['tested'] > 0 else 0
            print(f"📈 Taxa de sucesso: {success_rate:.1f}%")
            
            # Mostra os proxies que funcionaram
            working_details = [d for d in results['details'] if d['working']]
            if working_details:
                print(f"\n{Fore.GREEN}🟢 PROXIES FUNCIONANDO:{Style.RESET_ALL}")
                working_details.sort(key=lambda x: x['response_time'])
                for detail in working_details:
                    print(f"  • {detail['proxy']} - {detail['response_time']:.2f}s")
            
            return results
            
        except FileNotFoundError:
            print(f"❌ Arquivo não encontrado: {proxies_file}")
            return {"tested": 0, "working": 0, "failed": 0}
        except Exception as e:
            print(f"❌ Erro ao testar proxies: {e}")
            return {"tested": 0, "working": 0, "failed": 0}


class GmailTester:
    """Testa conectividade com Gmail."""
    
    def test_gmail_connection(self) -> bool:
        """Testa conexão com Gmail usando as credenciais do .env."""
        print(f"\n{Fore.BLUE}📧 Testando conexão com Gmail...{Style.RESET_ALL}")
        
        gmail_username = os.getenv("GMAIL_USERNAME")
        gmail_password = os.getenv("GMAIL_PASSWORD")
        
        if not gmail_username or not gmail_password:
            print(f"❌ Credenciais Gmail não configuradas no .env")
            print(f"   Configure: GMAIL_USERNAME e GMAIL_PASSWORD")
            return False
        
        try:
            reader = GmailReader(gmail_username, gmail_password)
            if reader.connect():
                print(f"✅ Conexão Gmail bem-sucedida para: {gmail_username}")
                
                # Testa leitura de pastas
                try:
                    reader.get_mailbox_list()
                    print(f"✅ Acesso às pastas do Gmail OK")
                except:
                    print(f"⚠️  Aviso: Possível problema no acesso às pastas")
                
                reader.disconnect()
                return True
            else:
                print(f"❌ Falha na conexão Gmail")
                print(f"   Verifique: usuário, senha de aplicativo, 2FA habilitado")
                return False
                
        except Exception as e:
            print(f"❌ Erro ao testar Gmail: {e}")
            return False


def create_sample_files():
    """Cria arquivos de exemplo se não existirem."""
    print(f"\n{Fore.YELLOW}📁 Criando arquivos de exemplo...{Style.RESET_ALL}")
    
    # Criar diretórios
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    # Exemplo proxies.csv
    if not os.path.exists(PROXY_CSV_FILE):
        with open(PROXY_CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['ip', 'port', 'username', 'password', 'status', 'country_code', 'country', 'city', 'last_checked'])
            writer.writerow(['1.2.3.4', '8000', 'user1', 'pass1', 'active', 'US', 'United States', 'New York', '2025-01-01'])
            writer.writerow(['5.6.7.8', '8001', 'user2', 'pass2', 'active', 'UK', 'United Kingdom', 'London', '2025-01-01'])
        print(f"✅ Arquivo de exemplo criado: {PROXY_CSV_FILE}")
    
    # Exemplo accounts_data.csv
    if not os.path.exists(ACCOUNTS_CSV_FILE):
        with open(ACCOUNTS_CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['email', 'full_name', 'username', 'password'])
            writer.writerow(['exemplo1@teste.com', 'João Silva', 'joao_silva_2025', 'MinhaSenh@123'])
            writer.writerow(['exemplo2@teste.com', 'Maria Santos', 'maria_santos_2025', 'OutraSenh@456'])
        print(f"✅ Arquivo de exemplo criado: {ACCOUNTS_CSV_FILE}")
    
    # Exemplo .env
    env_file = os.path.join(SCRIPT_DIR, '.env')
    if not os.path.exists(env_file):
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write("# Configurações do Gmail\n")
            f.write("GMAIL_USERNAME=seu_email@gmail.com\n")
            f.write("GMAIL_PASSWORD=sua_senha_de_aplicativo_aqui\n")
            f.write("\n# Configurações opcionais\n")
            f.write("GMAIL_SERVER=imap.gmail.com\n")
        print(f"✅ Arquivo de exemplo criado: {env_file}")
        print(f"   {Fore.YELLOW}⚠️  Configure suas credenciais reais no arquivo .env{Style.RESET_ALL}")


def main():
    """Função principal."""
    parser = argparse.ArgumentParser(description="Validação e preparação para automação Instagram")
    parser.add_argument('--test-proxies', action='store_true', help='Testar conectividade dos proxies')
    parser.add_argument('--test-gmail', action='store_true', help='Testar conexão com Gmail')
    parser.add_argument('--create-samples', action='store_true', help='Criar arquivos de exemplo')
    parser.add_argument('--proxies-file', default=PROXY_CSV_FILE, help='Arquivo de proxies')
    parser.add_argument('--accounts-file', default=ACCOUNTS_CSV_FILE, help='Arquivo de contas')
    
    args = parser.parse_args()
    
    print(f"{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗")
    print(f"║              🛠️  SETUP & VALIDATION TOOL                    ║")
    print(f"║                Instagram Account Creator                     ║")
    print(f"╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}")
    
    # Criar arquivos de exemplo se solicitado
    if args.create_samples:
        create_sample_files()
        return
    
    # Validação de arquivos
    validator = FileValidator()
    
    print(f"\n{Fore.GREEN}🔍 VALIDAÇÃO DE ARQUIVOS{Style.RESET_ALL}")
    print("=" * 50)
    
    proxy_stats = validator.validate_proxies_file(args.proxies_file)
    account_stats = validator.validate_accounts_file(args.accounts_file)
    
    # Testes opcionais
    if args.test_proxies and proxy_stats["valid"]:
        tester = ProxyTester()
        tester.test_proxies_batch(args.proxies_file)
    
    if args.test_gmail:
        gmail_tester = GmailTester()
        gmail_tester.test_gmail_connection()
    
    # Resumo final
    print(f"\n{Fore.GREEN}📋 RESUMO DA VALIDAÇÃO{Style.RESET_ALL}")
    print("=" * 50)
    
    if validator.errors:
        print(f"{Fore.RED}❌ ERROS ENCONTRADOS:{Style.RESET_ALL}")
        for error in validator.errors:
            print(f"  {error}")
    
    if validator.warnings:
        print(f"{Fore.YELLOW}⚠️  AVISOS:{Style.RESET_ALL}")
        for warning in validator.warnings:
            print(f"  {warning}")
    
    if not validator.errors:
        print(f"✅ Todos os arquivos são válidos!")
        print(f"🚀 Sistema pronto para execução da automação")
        
        if proxy_stats["active"] > 0 and account_stats["total"] > 0:
            max_threads = min(proxy_stats["active"], account_stats["total"])
            print(f"💡 Sugestão: Use até {max_threads} threads para melhor performance")
    else:
        print(f"❌ Corrija os erros antes de executar a automação")
        sys.exit(1)


if __name__ == "__main__":
    main()