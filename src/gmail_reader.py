import imaplib
import email
from email.header import decode_header
import os
import re
import time
from dotenv import load_dotenv

class GmailReader:
    def __init__(self, email_address, password, server=None):
        """
        Inicializa o leitor de Gmail

        Args:
            email_address: Seu endereço de email do Gmail
            password: Senha de aplicativo (não a senha normal da conta)
            server: Servidor IMAP (padrão: GMAIL_SERVER do .env ou imap.gmail.com)
        """
        self.email_address = email_address
        self.password = password
        self.server = server or os.getenv("GMAIL_SERVER", "imap.gmail.com")
        self.mail = None

    def connect(self):
        """Conecta ao servidor IMAP do Gmail"""
        try:
            self.mail = imaplib.IMAP4_SSL(self.server)
            self.mail.login(self.email_address, self.password)
            print(f"✓ Conectado com sucesso a {self.server}: {self.email_address}")
            return True
        except Exception as e:
            print(f"✗ Erro ao conectar: {e}")
            return False
    
    def get_mailbox_list(self):
        """Lista todas as caixas de email disponíveis"""
        try:
            result, mailboxes = self.mail.list()
            print("\nCaixas de email disponíveis:")
            for mailbox in mailboxes:
                print(f"  - {mailbox.decode()}")
        except Exception as e:
            print(f"Erro ao listar caixas: {e}")
    
    def read_social_emails(self, limit=10, from_email=None, target_email=None):
        """
        Lê emails não lidos da caixa InstaACC, filtrando pelo email de destino
        
        Args:
            limit: Número máximo de emails para processar
            from_email: Email específico do remetente (opcional)
            target_email: Email de destino para filtrar (opcional)
        """
        try:
            # Define a pasta alvo
            social_folders = ['InstaACC']
            selected = False
            for folder in social_folders:
                try:
                    result, data = self.mail.select(folder)
                    if result == 'OK':
                        print(f"✓ Pasta selecionada: {folder}")
                        selected = True
                        break
                except:
                    continue
            
            if not selected:
                print("⚠ Pasta InstaACC não encontrada. Tentando INBOX...")
                result, data = self.mail.select('INBOX')
                if result != 'OK':
                    raise Exception("Não foi possível selecionar nenhuma pasta")
            
            # Busca por emails não lidos
            if from_email and target_email:
                search_criteria = f'UNSEEN FROM "{from_email}" TO "{target_email}"'
                print(f"🔍 Buscando emails não lidos de {from_email} para {target_email}")
            elif from_email:
                search_criteria = f'UNSEEN FROM "{from_email}"'
                print(f"🔍 Buscando emails não lidos de: {from_email}")
            else:
                search_criteria = 'UNSEEN'
                print("🔍 Buscando todos os emails não lidos")
            
            result, messages = self.mail.search(None, search_criteria)
            
            if result != 'OK':
                print("Erro ao buscar emails")
                return []
            
            email_ids = messages[0].split()
            total_unread = len(email_ids)
            
            print(f"\n📧 Encontrados {total_unread} emails não lidos")
            
            if total_unread == 0:
                print("Nenhum email não lido encontrado.")
                return []
            
            emails_data = []
            
            for i, email_id in enumerate(email_ids[-limit:], 1):
                try:
                    result, msg_data = self.mail.fetch(email_id, '(RFC822)')
                    if result != 'OK':
                        continue
                    
                    email_message = email.message_from_bytes(msg_data[0][1])
                    email_info = self.extract_email_info(email_message)
                    email_info['id'] = email_id.decode()
                    
                    emails_data.append(email_info)
                    
                    print(f"\n--- Email {i}/{min(limit, total_unread)} ---")
                    print(f"De: {email_info['from']}")
                    print(f"Assunto: {email_info['subject']}")
                    print(f"Data: {email_info['date']}")
                    print(f"Prévia: {email_info['preview'][:100]}...")
                    
                except Exception as e:
                    print(f"Erro ao processar email {email_id}: {e}")
                    continue
            
            return emails_data
            
        except Exception as e:
            print(f"Erro ao ler emails da caixa InstaACC: {e}")
            return []
    
    def extract_email_info(self, email_message):
        """Extrai informações relevantes do email"""
        subject = self.decode_mime_words(email_message["Subject"])
        from_header = self.decode_mime_words(email_message["From"])
        date = email_message["Date"]
        body = self.get_email_body(email_message)
        return {
            'subject': subject or "Sem assunto",
            'from': from_header or "Remetente desconhecido",
            'date': date or "Data não disponível",
            'body': body,
            'preview': body[:200] if body else "Conteúdo não disponível"
        }
    
    def decode_mime_words(self, text):
        """Decodifica palavras MIME codificadas"""
        if not text:
            return ""
        decoded_parts = decode_header(text)
        decoded_text = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_text += part.decode(encoding or 'utf-8', errors='ignore')
            else:
                decoded_text += part
        return decoded_text
    
    def get_email_body(self, email_message):
        """Extrai o corpo do email (texto simples ou HTML)"""
        body = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if "attachment" in content_disposition:
                    continue
                if content_type == "text/plain":
                    charset = part.get_content_charset() or 'utf-8'
                    body = part.get_payload(decode=True).decode(charset, errors='ignore')
                    break
                elif content_type == "text/html" and not body:
                    charset = part.get_content_charset() or 'utf-8'
                    body = part.get_payload(decode=True).decode(charset, errors='ignore')
        else:
            charset = email_message.get_content_charset() or 'utf-8'
            body = email_message.get_payload(decode=True).decode(charset, errors='ignore')
        return body.strip()
    
    def read_emails_from_sender(self, sender_email, limit=10, target_email=None):
        """Função específica para ler emails não lidos de um remetente"""
        return self.read_social_emails(limit=limit, from_email=sender_email, target_email=target_email)
    
    def mark_as_read(self, email_id):
        """Marca um email específico como lido"""
        try:
            self.mail.store(email_id, '+FLAGS', '\\Seen')
            print(f"✓ Email {email_id} marcado como lido")
        except Exception as e:
            print(f"Erro ao marcar email como lido: {e}")
    
    def disconnect(self):
        """Desconecta do servidor IMAP"""
        if self.mail:
            self.mail.close()
            self.mail.logout()
            print("✓ Desconectado do Gmail")

def wait_for_instagram_code(email_address, password, account_email, timeout=60, max_retries=5):
    """
    Aguarda o código de verificação do Instagram enviado para o email da conta.
    
    Args:
        email_address: Email do Gmail para conectar
        password: Senha de aplicativo
        account_email: Email usado na criação da conta Instagram
        timeout: Tempo máximo de espera por tentativa (segundos)
        max_retries: Número máximo de tentativas
    
    Returns:
        str: Código de verificação ou None se falhar
    """
    reader = GmailReader(email_address, password)
    
    try:
        if not reader.connect():
            return None
        
        for attempt in range(max_retries):
            print(f"\nTentativa {attempt + 1}/{max_retries} para buscar código...")
            emails = reader.read_emails_from_sender("no-reply@mail.instagram.com", limit=1, target_email=account_email)
            
            if emails:
                body = emails[0]['body']
                # Extrai código (assumindo 6 dígitos)
                code_match = re.search(r'\b(\d{6})\b', body)
                if code_match:
                    code = code_match.group(1)
                    print(f"✓ Código encontrado: {code}")
                    reader.mark_as_read(emails[0]['id'])
                    return code
            
            print(f"✗ Código não encontrado. Aguardando {timeout} segundos...")
            time.sleep(timeout)
        
        print("⚠ Tempo esgotado. Nenhum código encontrado.")
        return None
    
    finally:
        reader.disconnect()

# Exemplo de uso na automação
def main():
    load_dotenv()
    gmail_username = os.getenv("GMAIL_USERNAME")
    gmail_password = os.getenv("GMAIL_PASSWORD")
    account_email = "igorvboas@gmail.com"  # Substitua pelo email da conta Instagram
    
    if not gmail_username or not gmail_password or not account_email:
        print("❌ Erro: GMAIL_USERNAME, GMAIL_PASSWORD e account_email devem estar definidos.")
        return
    
    print(f"📧 Iniciando automação para email: {account_email}")
    code = wait_for_instagram_code(gmail_username, gmail_password, account_email)
    
    if code:
        print(f"✅ Código obtido: {code}. Continue a automação com este código.")
    else:
        print("❌ Falha ao obter código. Verifique o email ou tente novamente.")

if __name__ == "__main__":
    main()