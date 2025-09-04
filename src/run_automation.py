#!/usr/bin/env python3
"""
Script de execução da automação de criação de contas Instagram em múltiplas threads.

Uso:
    python run_automation.py --threads 5 --proxies proxies.csv --accounts accounts_data.csv

Autor: Automação Instagram
Data: 2025
"""

import argparse
import sys
import os
import time
from datetime import datetime
from loguru import logger
import colorama
from colorama import Fore, Back, Style
from account_creator_multithreaded import MultiThreadAccountManager
from thread_config import CONFIG, ThreadStats
import logging
colorama.init()

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

def print_banner():
    """Exibe banner da aplicação."""
    banner = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════════════════════════╗
║                      🤖 INSTAGRAM ACCOUNT CREATOR                            ║
║                          Multi-Thread Automation                             ║
╚══════════════════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}


{Fore.YELLOW}🚀 Automação de criação de contas Instagram com execução paralela
📊 Suporte para múltiplas threads e proxies
📧 Verificação automática de email via Gmail{Style.RESET_ALL}

"""
    print(banner)

def print_stats(stats: dict):
    """Exibe estatísticas formatadas."""
    print(f"\n{Fore.GREEN}📊 ESTATÍSTICAS DE EXECUÇÃO:{Style.RESET_ALL}")
    print(f"{'='*50}")
    print(f"{Fore.GREEN}✅ Contas criadas com sucesso:{Style.RESET_ALL} {stats['success']}")
    print(f"{Fore.RED}❌ Falhas na criação:{Style.RESET_ALL} {stats['failed']}")
    print(f"{Fore.BLUE}📈 Total de tentativas:{Style.RESET_ALL} {stats['success'] + stats['failed']}")
    
    if stats['success'] + stats['failed'] > 0:
        success_rate = (stats['success'] / (stats['success'] + stats['failed'])) * 100
        print(f"{Fore.CYAN}📊 Taxa de sucesso:{Style.RESET_ALL} {success_rate:.1f}%")

def validate_files(proxies_file: str, accounts_file: str) -> bool:
    """Valida se os arquivos necessários existem."""
    missing_files = []
    
    if not os.path.exists(proxies_file):
        missing_files.append(proxies_file)
    
    if not os.path.exists(accounts_file):
        missing_files.append(accounts_file)
    
    if missing_files:
        print(f"{Fore.RED}❌ Arquivos não encontrados:{Style.RESET_ALL}")
        for file in missing_files:
            print(f"   📄 {file}")
        return False
    
    return True

def validate_environment():
    """Valida variáveis de ambiente necessárias."""
    required_vars = ['GMAIL_USERNAME', 'GMAIL_PASSWORD']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"{Fore.RED}❌ Variáveis de ambiente não configuradas:{Style.RESET_ALL}")
        for var in missing_vars:
            print(f"   🔐 {var}")
        print(f"\n{Fore.YELLOW}💡 Configure as variáveis no arquivo .env:{Style.RESET_ALL}")
        print(f"   GMAIL_USERNAME=seu_email@gmail.com")
        print(f"   GMAIL_PASSWORD=sua_senha_de_aplicativo")
        return False
    
    return True

def count_file_lines(filepath: str) -> int:
    """Conta número de linhas em um arquivo CSV (excluindo cabeçalho)."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return sum(1 for line in f) - 1  # Subtrai cabeçalho
    except:
        return 0

def show_execution_preview(threads: int, proxies_file: str, accounts_file: str):
    """Mostra prévia da execução antes de iniciar."""
    proxy_count = count_file_lines(proxies_file)
    account_count = count_file_lines(accounts_file)
    
    print(f"\n{Fore.BLUE}📋 PRÉVIA DA EXECUÇÃO:{Style.RESET_ALL}")
    print(f"{'='*40}")
    print(f"{Fore.CYAN}🔧 Threads configuradas:{Style.RESET_ALL} {threads}")
    print(f"{Fore.CYAN}🌐 Proxies disponíveis:{Style.RESET_ALL} {proxy_count}")
    print(f"{Fore.CYAN}👤 Contas para criar:{Style.RESET_ALL} {account_count}")
    
    actual_threads = min(threads, proxy_count, account_count)
    print(f"{Fore.GREEN}⚡ Threads que serão usadas:{Style.RESET_ALL} {actual_threads}")
    
    if actual_threads < threads:
        print(f"{Fore.YELLOW}⚠️  Threads limitadas por recursos disponíveis{Style.RESET_ALL}")
    
    estimated_time = account_count * 2  # Estimativa: 2 minutos por conta
    print(f"{Fore.MAGENTA}⏱️  Tempo estimado:{Style.RESET_ALL} ~{estimated_time} minutos")

def get_user_confirmation() -> bool:
    """Solicita confirmação do usuário para continuar."""
    while True:
        response = input(f"\n{Fore.YELLOW}🤔 Deseja continuar com a execução? (s/n): {Style.RESET_ALL}").lower().strip()
        if response in ['s', 'sim', 'y', 'yes']:
            return True
        elif response in ['n', 'não', 'nao', 'no']:
            return False
        print(f"{Fore.RED}❓ Por favor, responda 's' para sim ou 'n' para não{Style.RESET_ALL}")

def setup_logging(verbose: bool = False):
    """Configura sistema de logging."""
    log_level = "DEBUG" if verbose else "INFO"
    
    # Remove handlers existentes
    logger.remove()
    
    # Log para console
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        colorize=True
    )
    
    # Log para arquivo
    main_log_file = os.path.join(LOGS_DIR, "automation_main.log")
    logger.add(
        main_log_file,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        rotation="10 MB",
        retention="7 days"
    )

def monitor_execution(manager: MultiThreadAccountManager):
    """Monitora execução em tempo real (versão simplificada)."""
    print(f"\n{Fore.GREEN}🚀 Execução iniciada! Aguarde...{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}📝 Logs detalhados em: logs/automation_main.log{Style.RESET_ALL}")

def main():
    """Função principal do script."""
    parser = argparse.ArgumentParser(
        description="Automação de criação de contas Instagram com múltiplas threads",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python run_automation.py --threads 3
  python run_automation.py --threads 5 --proxies meus_proxies.csv
  python run_automation.py --threads 2 --accounts minhas_contas.csv --verbose
        """
    )
    
    parser.add_argument(
        '--threads', '-t',
        type=int,
        default=3,
        help='Número de threads para execução paralela (padrão: 3)'
    )
    
    parser.add_argument(
        '--proxies', '-p',
        type=str,
        default=PROXY_CSV_FILE,
        help=f'Arquivo CSV com lista de proxies (padrão: {PROXY_CSV_FILE})'
    )
    
    parser.add_argument(
        '--accounts', '-a',
        type=str,
        default=ACCOUNTS_CSV_FILE,
        help=f'Arquivo CSV com dados das contas (padrão: {ACCOUNTS_CSV_FILE})'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Ativar logs detalhados (debug)'
    )
    
    parser.add_argument(
        '--no-confirm',
        action='store_true',
        help='Pular confirmação de execução'
    )
    
    parser.add_argument(
        '--fresh-start',
        action='store_true',
        help='Limpar arquivo de resultados antes de começar (nova execução)'
    )
    
    args = parser.parse_args()
    
    # Setup inicial
    print_banner()
    
    setup_logging(args.verbose)
    
    # Validações
    logger.info("Iniciando validações...")
    
    if not validate_environment():
        sys.exit(1)
    
    if not validate_files(args.proxies, args.accounts):
        sys.exit(1)
    
    # Prévia da execução
    show_execution_preview(args.threads, args.proxies, args.accounts)
    
    # Confirmação do usuário
    if not args.no_confirm and not get_user_confirmation():
        print(f"\n{Fore.YELLOW}👋 Execução cancelada pelo usuário{Style.RESET_ALL}")
        sys.exit(0)
    
    # Execução principal
    try:
        print(f"\n{Fore.GREEN}{'='*60}")
        print(f"🎬 INICIANDO AUTOMAÇÃO")
        print(f"{'='*60}{Style.RESET_ALL}")
        
        start_time = time.time()
        
        # Criar manager e executar
        manager = MultiThreadAccountManager(max_threads=args.threads)
        
        # Limpa arquivo anterior se solicitado
        if args.fresh_start:
            results_file = os.path.join(DATA_DIR, "accounts_created.csv")
            if os.path.exists(results_file):
                os.remove(results_file)
                print(f"🗑️ Arquivo de resultados anterior removido")
        
        monitor_execution(manager)
        
        results = manager.run(
            proxies_file=args.proxies,
            accounts_file=args.accounts
        )
        
        execution_time = time.time() - start_time
        
        # Resultados finais
        print(f"\n{Fore.GREEN}{'='*60}")
        print(f"🎉 EXECUÇÃO CONCLUÍDA")
        print(f"{'='*60}{Style.RESET_ALL}")
        
        print_stats(results)
        print(f"{Fore.MAGENTA}⏱️ Tempo total de execução:{Style.RESET_ALL} {execution_time:.2f} segundos")
        results_file = os.path.join(DATA_DIR, "accounts_created.csv")
        print(f"{Fore.CYAN}📁 Resultados salvos em:{Style.RESET_ALL} {results_file}")
        
        # Resumo por thread
        if results.get('results'):
            print(f"\n{Fore.BLUE}📊 RESUMO POR THREAD:{Style.RESET_ALL}")
            thread_summary = {}
            for result in results['results']:
                thread_id = result['thread_id']
                if thread_id not in thread_summary:
                    thread_summary[thread_id] = {'success': 0, 'failed': 0}
                
                if result['success']:
                    thread_summary[thread_id]['success'] += 1
                else:
                    thread_summary[thread_id]['failed'] += 1
            
            for thread_id, stats in thread_summary.items():
                success_rate = (stats['success'] / (stats['success'] + stats['failed'])) * 100
                print(f"  Thread {thread_id}: {stats['success']}✅ {stats['failed']}❌ ({success_rate:.1f}%)")
        
        logger.info("Automação concluída com sucesso")
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}🛑 Execução interrompida pelo usuário{Style.RESET_ALL}")
        logger.warning("Execução interrompida pelo usuário")
        sys.exit(130)
        
    except Exception as e:
        print(f"\n{Fore.RED}💥 Erro durante execução: {e}{Style.RESET_ALL}")
        logger.error(f"Erro durante execução: {e}")
        sys.exit(1)
        
    finally:
        main_log_file = os.path.join(LOGS_DIR, "automation_main.log")
        thread_logs_dir = os.path.join(LOGS_DIR, "thread_*.log")
        print(f"\n{Fore.CYAN}📝 Logs salvos em: {main_log_file}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}🔍 Para logs detalhados por thread, veja: {thread_logs_dir}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()