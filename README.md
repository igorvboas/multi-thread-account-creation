# Web Automation Framework

Um framework Python para automação web usando Selenium com recursos anti-detecção, suporte a proxies e execução multi-thread.

## Estrutura do Projeto

```
MULTI-THREAD ACCOUNT CREATION/
├── src/
│   ├── account_creator_multithreaded.py   # Gerenciador de threads
│   ├── anti_detection.py                  # Sistema anti-detecção
│   ├── browser_handler.py                 # Gerenciador de browser
│   ├── gmail_reader.py                    # Leitor de emails
│   ├── run_automation.py                  # Script principal de execução
│   ├── setup_and_validate.py              # Setup e validações iniciais
│   ├── testing_proxy.py                   # Teste de proxies
│   └── thread_config.py                   # Configurações globais de threads
├── config/
│   ├── accounts_data.csv                  # Dados de entrada
│   ├── config.yaml                        # Configurações gerais
│   └── proxies.csv                        # Lista de proxies
├── data/
│   └── accounts_created.csv               # Saída com contas criadas
├── logs/                                  # Logs do sistema
├── screenshots/                           # Prints gerados pela automação
├── venv/                                  # Ambiente virtual (ignorar no Git)
├── .env                                   # Variáveis de ambiente
├── .gitignore                             # Arquivo de exclusões do Git
├── interface_navegador.py                 # Interface gráfica/navegador
├── proxy_auth_plugin.zip                  # Plugin para proxy com autenticação
├── README.md                              # Documentação do projeto
└── requirements.txt                       # Dependências do projeto
```

## Instalação

### 1. Dependências Python
```bash
pip install selenium
pip install undetected-chromedriver
pip install loguru
pip install colorama
pip install fake-useragent
pip install PyYAML
pip install python-dotenv
```

### 2. Chrome/Chromium
Certifique-se de ter o Google Chrome instalado no sistema.

## Configuração

### 1. Variáveis de Ambiente
Crie um arquivo `.env` na raiz do projeto:

```env
GMAIL_USERNAME=seu_email@gmail.com
GMAIL_PASSWORD=sua_senha_de_aplicativo
GMAIL_SERVER=imap.gmail.com
```

### 2. Arquivo de Proxies
Configure `proxies.csv` com o formato:

```csv
ip,port,username,password,country,city,status
192.168.1.1,8080,user1,pass1,Brazil,São Paulo,active
192.168.1.2,8080,user2,pass2,USA,New York,active
```

### 3. Dados de Entrada
Configure `accounts_data.csv`:

```csv
email,full_name,username,password
test@example.com,Test User,testuser,password123
```

### 4. Configuração do Sistema
Edite `config/config.yaml`:

```yaml
browser:
  headless: false
  user_agents: []

delays:
  min_action: 1
  max_action: 3

proxies:
  use_proxies: true
```

## Uso

### Execução Básica
```bash
python src/run_automation.py --threads 3
```

### Parâmetros Disponíveis
```bash
python src/run_automation.py \
  --threads 5 \
  --proxies custom_proxies.csv \
  --accounts custom_accounts.csv \
  --verbose \
  --no-confirm \
  --fresh-start
```

**Parâmetros:**
- `--threads, -t`: Número de threads paralelas (padrão: 3)
- `--proxies, -p`: Arquivo CSV de proxies personalizado
- `--accounts, -a`: Arquivo CSV de contas personalizado
- `--verbose, -v`: Logs detalhados (debug)
- `--no-confirm`: Pular confirmação de execução
- `--fresh-start`: Limpar arquivo de resultados anterior

## Características Técnicas

### Anti-Detecção
- User agents dinâmicos
- Fingerprinting de browser personalizado
- Configurações CDP avançadas
- Randomização de canvas e propriedades

### Gerenciamento de Proxies
- Rotação automática de proxies
- Suporte a autenticação
- Verificação de status
- Distribuição por threads

### Multi-Threading
- Execução paralela configurável
- Isolamento de recursos por thread
- Logs individuais por thread
- Tratamento robusto de erros

### Logs e Monitoramento
- Logs estruturados com Loguru
- Interface colorizada
- Estatísticas em tempo real
- Relatórios de execução

## Estrutura de Logs

```
logs/
├── automation_main.log        # Log principal
├── thread_1.log              # Logs da thread 1
├── thread_2.log              # Logs da thread 2
└── ...
```

## Saída de Dados

Os resultados são salvos em `data/accounts_created.csv`:

```csv
email,username,password,status,created_at,fingerprint,proxy_used,thread_id
test@example.com,testuser,pass123,success,Mon Jan 1 12:00:00 2024,{...},192.168.1.1:8080,1
```

## Configurações Avançadas

### Timeouts
Configurados em `thread_config.py`:
- `PAGE_LOAD_TIMEOUT`: 30 segundos
- `ELEMENT_WAIT_TIMEOUT`: 20 segundos
- `EMAIL_CHECK_INTERVAL`: 15 segundos

### Performance
- `MAX_THREADS`: Limite máximo de threads simultâneas
- `THREAD_TIMEOUT`: Timeout por thread
- Otimizações automáticas de memória

## Troubleshooting

### Problemas Comuns

**Browser não inicializa:**
- Verificar instalação do Chrome
- Verificar permissões do sistema
- Tentar modo não-headless para debug

**Proxies não funcionam:**
- Verificar conectividade dos proxies
- Validar credenciais de autenticação
- Testar com `USE_PROXIES = False`

**Elementos não encontrados:**
- Adicionar pausas manuais com `input()`
- Verificar seletores XPath
- Usar screenshots para debug

**Timeouts frequentes:**
- Aumentar valores em `thread_config.py`
- Reduzir número de threads
- Verificar qualidade da conexão

### Debug Mode
Para debug detalhado:

```bash
python src/run_automation.py --threads 1 --verbose
```

## Limitações

- Requer Chrome/Chromium instalado
- Dependente de seletores específicos da página
- Performance limitada pela qualidade dos proxies
- Necessita configuração manual inicial

## Contribuição

Para modificar o comportamento:

1. **Seletores**: Edite os XPath em `account_creator_multithreaded.py`
2. **Anti-detecção**: Ajuste configurações em `anti_detection.py`
3. **Timeouts**: Modifique valores em `thread_config.py`
4. **Proxies**: Implemente nova lógica em `MultiThreadAccountManager`

## Aviso Legal

Este framework é destinado apenas para fins educacionais e de teste em ambientes controlados. O uso deve respeitar os termos de serviço das plataformas e a legislação aplicável.
