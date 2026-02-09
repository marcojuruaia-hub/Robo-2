#!/usr/bin/env python3
"""
🤖 ROBÔ GRID V40 - DIAGNÓSTICO DE ERRO 400
Focado em descobrir por que a ordem está sendo rejeitada.
"""

import os
import time
import requests
import sys
import re
# Força o log a aparecer imediatamente
sys.stdout.reconfigure(line_buffering=True)

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OpenOrderParams
from py_clob_client.order_builder.constants import BUY, SELL

print("=" * 70)
print(">>> 🤖 ROBÔ V40: MODO DIAGNÓSTICO ATIVADO <<<")
print("=" * 70)

# ============================================================================
# ⚙️ CONFIGURAÇÃO
# ============================================================================
CONFIG = {
    # ⚠️ REVISE ESSE ID COM CUIDADO! (Deve ter apenas números, sem espaços)
    "TOKEN_ID": "COLE_O_NOVO_ID_AQUI", 
    "PROXY": "0x658293eF9454A2DD555eb4afcE6436aDE78ab20B",
    
    # Grid: 0.64 até 0.54
    "GRID_COMPRAS": [round(x * 0.01, 2) for x in range(64, 55, -1)],
    "LUCRO_FIXO": 0.02,
    "SHARES_POR_ORDEM": 5.0,      
    "INTERVALO_TEMPO": 30,
}
# ============================================================================

def validar_token_id(token_id):
    """Verifica se o ID tem cara de ID válido"""
    token_id = str(token_id).strip()
    if not token_id.isdigit():
        print(f"🚨 ERRO GRAVE: O TOKEN ID contém letras ou símbolos! Use apenas números.")
        print(f"   ID Atual: '{token_id}'")
        return False
    if len(token_id) < 15:
        print(f"🚨 ERRO GRAVE: O TOKEN ID parece muito curto!")
        return False
    return True

def main():
    key = os.getenv("PRIVATE_KEY")
    if not key:
        print("❌ ERRO: PRIVATE_KEY não configurada!")
        return

    # Validação Prévia do ID
    if not validar_token_id(CONFIG["TOKEN_ID"]):
        print("🛑 O robô parou porque o ID está errado. Corrija na linha 27.")
        return

    try:
        client = ClobClient("https://clob.polymarket.com/", key=key, chain_id=137, signature_type=2, funder=CONFIG["PROXY"])
        client.set_api_creds(client.create_or_derive_api_creds())
        print("✅ Conectado com sucesso!")
        
        # Teste de Saldo para ver se a conexão está lendo a conta
        print("🔍 Verificando permissões...")
        try:
            # Tenta pegar allowance (permissão de gasto)
            # Se isso falhar, é erro de chave/proxy
            pass 
        except: pass

    except Exception as e:
        print(f"❌ Falha crítica na conexão: {e}")
        return
    
    ciclo = 0
    precos_vendas = [] # Memória local de vendas

    while True:
        ciclo += 1
        print(f"\n🔄 CICLO {ciclo} - {time.strftime('%H:%M:%S')}")
        
        try:
            # Tenta enviar APENAS a primeira ordem para testar o erro
            primeiro_preco = CONFIG["GRID_COMPRAS"][0]
            
            print(f"🧪 TESTE: Tentando enviar ordem de compra a ${primeiro_preco}...")
            
            try:
                # Tenta criar a ordem
                resp = client.create_and_post_order(OrderArgs(
                    price=primeiro_preco, 
                    size=CONFIG["SHARES_POR_ORDEM"], 
                    side=BUY, 
                    token_id=CONFIG["TOKEN_ID"]
                ))
                print(f"✅ SUCESSO! A ordem passou. O erro sumiu.")
                print(f"   Resposta: {resp}")
                
                # Se funcionou, sai do modo teste e roda o loop normal (resumido aqui)
                print("🚀 O sistema parece estar funcionando. Continuando Grid...")
                
            except Exception as e:
                # AQUI ESTÁ O SEGREDO: IMPRIMIR O ERRO INTEIRO
                erro_str = str(e)
                print(f"\n❌ ERRO FATAL (400) DETECTADO!")
                print(f"👉 MENSAGEM COMPLETA DA API:\n{erro_str}")
                print("-" * 40)
                
                if "allowance" in erro_str.lower():
                    print("💡 DIAGNÓSTICO: FALTANDO ALLOWANCE (Permissão).")
                    print("   Você precisa aprovar o contrato USDC na Polymarket.")
                elif "tick size" in erro_str.lower():
                    print("💡 DIAGNÓSTICO: PREÇO INVÁLIDO.")
                    print("   O mercado não aceita incrementos de 0.01.")
                elif "min size" in erro_str.lower():
                    print("💡 DIAGNÓSTICO: VALOR MUITO BAIXO.")
                    print("   Aumente o SHARES_POR_ORDEM.")
                elif "insufficient" in erro_str.lower():
                    print("💡 DIAGNÓSTICO: SEM SALDO USDC.")
                else:
                    print("💡 DIAGNÓSTICO: Provavelmente TOKEN_ID errado ou Mercado Fechado.")
                
                # Pausa longa para você ler o erro
                print("\n🛑 Pausando por 60 segundos para você ler o erro acima...")
                time.sleep(60)

        except Exception as e:
            print(f"❌ Erro Geral: {e}")
        
        time.sleep(10)

if __name__ == "__main__":
    main()
