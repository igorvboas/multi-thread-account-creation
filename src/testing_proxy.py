#!/usr/bin/env python3
"""
Script para testar conexão de proxies
Autor: Assistente Claude
Data: 2025-09-01
"""

import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from typing import List, Dict, Tuple
import sys

class ProxyTester:
    def __init__(self, timeout=10, max_workers=5):
        """
        Inicializa o testador de proxy
        
        Args:
            timeout (int): Timeout para requisições em segundos
            max_workers (int): Número máximo de threads simultâneas
        """
        self.timeout = timeout
        self.max_workers = max_workers
        self.test_urls = [
            'http://httpbin.org/ip',
            'https://httpbin.org/ip',
            'http://icanhazip.com',
            'https://api.ipify.org?format=json'
        ]
        
    def test_single_proxy(self, proxy_info: Dict) -> Dict:
        """
        Testa um único proxy
        
        Args:
            proxy_info (dict): Informações do proxy contendo ip, porta, username, password
            
        Returns:
            dict: Resultado do teste
        """
        proxy_ip = proxy_info.get('ip')
        proxy_port = proxy_info.get('port')
        username = proxy_info.get('username', '')
        password = proxy_info.get('password', '')
        
        # Configura o proxy
        if username and password:
            proxy_url = f"http://{username}:{password}@{proxy_ip}:{proxy_port}"
        else:
            proxy_url = f"http://{proxy_ip}:{proxy_port}"
            
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        result = {
            'proxy': f"{proxy_ip}:{proxy_port}",
            'status': 'failed',
            'response_time': None,
            'real_ip': None,
            'error': None,
            'test_url': None
        }
        
        start_time = time.time()
        
        for test_url in self.test_urls:
            try:
                print(f"🔍 Testando {proxy_ip}:{proxy_port} com {test_url}")
                
                response = requests.get(
                    test_url,
                    proxies=proxies,
                    timeout=self.timeout,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                )
                
                response_time = round(time.time() - start_time, 2)
                
                if response.status_code == 200:
                    # Extrai o IP real da resposta
                    try:
                        if 'json' in response.headers.get('content-type', '').lower():
                            data = response.json()
                            real_ip = data.get('origin') or data.get('ip')
                        else:
                            real_ip = response.text.strip()
                    except:
                        real_ip = "IP não identificado"
                    
                    result.update({
                        'status': 'success',
                        'response_time': response_time,
                        'real_ip': real_ip,
                        'test_url': test_url
                    })
                    print(f"✅ {proxy_ip}:{proxy_port} - OK ({response_time}s) - IP: {real_ip}")
                    break
                    
            except requests.exceptions.ProxyError as e:
                result['error'] = f"Erro de proxy: {str(e)}"
                print(f"❌ {proxy_ip}:{proxy_port} - Erro de proxy: {str(e)}")
                
            except requests.exceptions.Timeout as e:
                result['error'] = f"Timeout: {str(e)}"
                print(f"⏰ {proxy_ip}:{proxy_port} - Timeout")
                
            except requests.exceptions.ConnectionError as e:
                result['error'] = f"Erro de conexão: {str(e)}"
                print(f"🔌 {proxy_ip}:{proxy_port} - Erro de conexão")
                
            except Exception as e:
                result['error'] = f"Erro geral: {str(e)}"
                print(f"❓ {proxy_ip}:{proxy_port} - Erro: {str(e)}")
        
        if result['status'] == 'failed' and result['response_time'] is None:
            result['response_time'] = round(time.time() - start_time, 2)
            
        return result
    
    def test_multiple_proxies(self, proxy_list: List[Dict]) -> List[Dict]:
        """
        Testa múltiplos proxies simultaneamente
        
        Args:
            proxy_list (list): Lista de proxies para testar
            
        Returns:
            list: Lista com resultados dos testes
        """
        print(f"\n🚀 Iniciando teste de {len(proxy_list)} proxies...")
        print(f"⚙️  Configurações: Timeout={self.timeout}s, Workers={self.max_workers}")
        print("-" * 80)
        
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_proxy = {
                executor.submit(self.test_single_proxy, proxy): proxy 
                for proxy in proxy_list
            }
            
            for future in as_completed(future_to_proxy):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    proxy = future_to_proxy[future]
                    results.append({
                        'proxy': f"{proxy.get('ip')}:{proxy.get('port')}",
                        'status': 'failed',
                        'error': f"Erro na thread: {str(e)}",
                        'response_time': None,
                        'real_ip': None,
                        'test_url': None
                    })
        
        return results
    
    def print_summary(self, results: List[Dict]):
        """
        Imprime um resumo dos resultados
        
        Args:
            results (list): Lista com resultados dos testes
        """
        total = len(results)
        success = len([r for r in results if r['status'] == 'success'])
        failed = total - success
        
        print("\n" + "=" * 80)
        print("📊 RESUMO DOS TESTES")
        print("=" * 80)
        print(f"Total de proxies testados: {total}")
        print(f"✅ Funcionando: {success} ({success/total*100:.1f}%)")
        print(f"❌ Com falha: {failed} ({failed/total*100:.1f}%)")
        
        # Proxies que funcionaram
        working_proxies = [r for r in results if r['status'] == 'success']
        if working_proxies:
            print(f"\n🟢 PROXIES FUNCIONANDO:")
            working_proxies.sort(key=lambda x: x['response_time'])
            for proxy in working_proxies:
                print(f"  • {proxy['proxy']} - {proxy['response_time']}s - IP: {proxy['real_ip']}")
        
        # Proxies com falha
        failed_proxies = [r for r in results if r['status'] == 'failed']
        if failed_proxies:
            print(f"\n🔴 PROXIES COM FALHA:")
            for proxy in failed_proxies[:10]:  # Mostra apenas os primeiros 10
                error_msg = proxy['error'][:60] + "..." if len(proxy['error']) > 60 else proxy['error']
                print(f"  • {proxy['proxy']} - {error_msg}")
            if len(failed_proxies) > 10:
                print(f"  ... e mais {len(failed_proxies) - 10} proxies com falha")

def main():
    """Função principal"""
    
    # Lista de proxies baseada na imagem enviada
    # Você pode modificar esta lista com seus proxies
    proxy_list = [
        {'ip': '63.246.130.70', 'port': 6271, 'username': 'lzrldpsg', 'password': '0uw6l6wk2bp8'},
        {'ip': '45.39.157.52', 'port': 9084, 'username': 'lzrldpsg', 'password': '0uw6l6wk2bp8'},
        {'ip': '82.23.103.136', 'port': 7863, 'username': 'lzrldpsg', 'password': '0uw6l6wk2bp8'},
        {'ip': '46.203.41.236', 'port': 5737, 'username': 'lzrldpsg', 'password': '0uw6l6wk2bp8'},
        {'ip': '192.53.142.208', 'port': 5905, 'username': 'lzrldpsg', 'password': '0uw6l6wk2bp8'},
        {'ip': '46.203.44.19', 'port': 6018, 'username': 'lzrldpsg', 'password': '0uw6l6wk2bp8'},
        {'ip': '82.26.114.254', 'port': 6956, 'username': 'lzrldpsg', 'password': '0uw6l6wk2bp8'},
        {'ip': '45.196.50.191', 'port': 6513, 'username': 'lzrldpsg', 'password': '0uw6l6wk2bp8'},
        {'ip': '46.203.137.47', 'port': 6044, 'username': 'lzrldpsg', 'password': '0uw6l6wk2bp8'},
        {'ip': '96.62.180.48', 'port': 7758, 'username': 'lzrldpsg', 'password': '0uw6l6wk2bp8'},
    ]
    
    # Configurações da API (caso seja necessária)
    API_KEY = "zjqjsduh5zzq0ve7b0d8i62ol0jk56ksujcl0a1"  # Sua API key da imagem
    
    # Cria o testador
    tester = ProxyTester(timeout=15, max_workers=3)
    
    # Executa os testes
    results = tester.test_multiple_proxies(proxy_list)
    
    # Mostra o resumo
    tester.print_summary(results)
    
    # Salva os resultados em arquivo JSON
    timestamp = int(time.time())
    filename = f"proxy_test_results_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Resultados salvos em: {filename}")
    
    # Retorna apenas os proxies que funcionam
    working_proxies = [r for r in results if r['status'] == 'success']
    return working_proxies

if __name__ == "__main__":
    try:
        working = main()
        print(f"\n🎉 Script finalizado! {len(working)} proxies funcionando.")
    except KeyboardInterrupt:
        print("\n\n⏹️  Script interrompido pelo usuário.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erro fatal: {str(e)}")
        sys.exit(1)