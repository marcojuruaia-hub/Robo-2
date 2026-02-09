#!/usr/bin/env python3
"""
🤖 ROBÔ GRID V42 - OPERAÇÃO REAL (SINTAXE CORRIGIDA)
Baseado no guia 'bits_and_bobs':
- Usa DATA_API para ler posições reais (evita Status Desconhecido)
- Usa CLOB_API para operar
- Proteção contra erro NoneType e SyntaxError
"""

import os
import time
import requests
import sys

# Força o log a aparecer imediatamente no Railway
sys.stdout.reconfigure(line_buffering=True)

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OpenOrderParams
from py_clob_client.order_builder.constants import BUY, SELL

print("=" * 70)
print(">>> 🤖 ROBÔ V42: SINTAXE E LÓGICA CORRIGIDAS <<<")
print("=" * 70)

# ============================================================================
# ⚙️ CONFIGURAÇÃO
# ============================================================================
CONFIG = {
    # ID DO MERCADO (Bitcoin Up or Down Feb 8/Main)
    "TOKEN_ID": "24120579393151285531790392365655515414663383379081658053153655752666989210807", 
    "PROXY": "0x658293eF9454A2DD555eb4afcE6436aDE78ab20B",
    
    # Grid de Compra: Começa em 0.64 e vai descendo até 0.55
    "GRID_COMPRAS": [round(x * 0.01, 2) for x in range(66, 50, -2)],
    
    "LUCRO_FIXO": 0.05,           # Ex: Compra 0.64 -> Vende 0.66
    "SHARES_POR_ORDEM": 5.0,      # Tamanho da ordem
    "INTERVALO_TEMPO": 120,        # Segundos entre ciclos
}

# URL descoberta no guia bits_and_bobs para ler saldo real
DATA_API = "https://data-api.polymarket.com"
# ============================================================================

def safe_float(value):
    """
    Converte valores da API para float com segurança.
    Evita o erro 'NoneType' se a API devolver vazio.
    """
    try:
        if value is None:
            return 0.0
        return float(value)
    except:
        return 0.0

def obter_posicao_real(asset_id, user_address):
    """
    Consulta a API de Dados (Conforme Seção 11 do Guia)
    Retorna quantas shares você REALMENTE tem na carteira.
    """
    try:
        url = f"{DATA_API}/positions"
        params = {"user": user_address, "asset_id": asset_id}
        resp = requests.get(url, params=params).json()
        
        if isinstance(resp, list):
            for pos in resp:
                if pos.get("asset_id") == asset_id:
                    return safe_float(pos.get("size", 0))
        return 0.0
    except Exception as e:
        print(f"⚠️ Erro ao ler Data API: {e}")
        return 0.0

def calcular_qtd(preco):
    # Garante que a ordem tenha tamanho financeiro mínimo (~$1)
    return 5.0 if preco > 0.20 else round(1.0 / preco, 2)

def main():
    key = os.getenv("PRIVATE_KEY")
    if not key:
        print("❌ ERRO: PRIVATE_KEY não configurada!")
        return
    
    try:
        # Conexão principal (CLOB)
        client = ClobClient("https://clob.polymarket.com/", key=key, chain_id=137, signature_type=2, funder=CONFIG["PROXY"])
        client.set_api_creds(client.create_or_derive_api_creds())
        print("✅ Conectado com sucesso!")
    except Exception as e:
        print(f"❌ Falha na conexão: {e}")
        return
    
    ciclo = 0
    vendas_memoria = [] # Memória de curto prazo para evitar duplicação

    while True:
        ciclo += 1
        print(f"\n🔄 CICLO {ciclo} - {time.strftime('%H:%M:%S')}")
        
        try:
            # -------------------------------------------------------
            # 1. MAPEAMENTO (LENDO O MERCADO)
            # -------------------------------------------------------
            todas = client.get_orders(OpenOrderParams())
            minhas = [o for o in todas if o.get('asset_id') == CONFIG["TOKEN_ID"]]
            
            # Separa o que é compra e o que é venda
            compras_abertas = []
            vendas_abertas = []
            
            for o in minhas:
                p = safe_float(o.get('price'))
                s = o.get('side')
                if s == BUY: compras_abertas.append(round(p, 2))
                if s == SELL: vendas_abertas.append(round(p, 2))
            
            # Adiciona vendas recém-criadas (memória) à lista de verificação
            for v in vendas_memoria:
                if v not in vendas_abertas:
                    vendas_abertas.append(v)

            # -------------------------------------------------------
            # 2. RECONCILIAÇÃO (LENDO A CARTEIRA - GUIDE SEC. 11)
            # -------------------------------------------------------
            saldo_real = obter_posicao_real(CONFIG["TOKEN_ID"], CONFIG["PROXY"])
            
            # Soma segura das cotas já comprometidas em ordens de venda
            travado_em_ordens = sum([safe_float(o.get('size')) for o in minhas if o.get('side') == SELL])
            
            # Cotas Soltas = O que tenho na mão - O que já pus pra vender
            cotas_soltas = saldo_real - travado_em_ordens
            cotas_soltas = round(cotas_soltas, 2) # Arredonda para evitar 0.000001
            
            print(f"📊 SALDO: {saldo_real} | TRAVADO: {travado_em_ordens} | 🟢 SOLTAS: {cotas_soltas}")
            
            # -------------------------------------------------------
            # 3. CRIAÇÃO DE VENDAS (RECUPERAÇÃO DE LUCRO)
            # -------------------------------------------------------
            if cotas_soltas >= 1.0:
                print(f"💡 DETECTADO: {cotas_soltas} shares precisando de venda...")
                
                # Tenta casar as cotas soltas com os níveis do grid
                for p_compra in CONFIG["GRID_COMPRAS"]:
                    if cotas_soltas < 1.0: break
                    
                    p_venda = round(p_compra + CONFIG["LUCRO_FIXO"], 2)
                    
                    # Só cria a venda se ela AINDA NÃO EXISTIR
                    if p_venda not in vendas_abertas:
                        qtd = calcular_qtd(p_compra)
                        if qtd > cotas_soltas: qtd = cotas_soltas
                        
                        try:
                            print(f"💰 VENDENDO: ${p_venda} (Baseado em ${p_compra})")
                            client.create_and_post_order(OrderArgs(
                                price=p_venda, size=qtd, side=SELL, token_id=CONFIG["TOKEN_ID"]
                            ))
                            # Atualiza contadores locais
                            cotas_soltas -= qtd
                            vendas_abertas.append(p_venda)
                            vendas_memoria.append(p_venda)
                        except Exception as e:
                            print(f"❌ Erro ao criar Venda: {e}")

            # Limpa memória antiga
            if len(vendas_memoria) > 10: vendas_memoria = vendas_memoria[-10:]

            # -------------------------------------------------------
            # 4. MANUTENÇÃO DO GRID (COMPRAS INTELIGENTES)
            # -------------------------------------------------------
            print("🔵 VERIFICANDO GRID...")
            novas_compras = 0
            
            for p in CONFIG["GRID_COMPRAS"]:
                p_lucro = round(p + CONFIG["LUCRO_FIXO"], 2)
                
                # Regras de bloqueio de compra:
                ja_tem_compra = p in compras_abertas
                tem_venda_esperando = p_lucro in vendas_abertas
                
                if ja_tem_compra:
                    # print(f"   🆗 ${p}: Já ativo.")
                    continue
                
                if tem_venda_esperando:
                    print(f"   ⏳ ${p}: Pausado (Aguardando venda a ${p_lucro})")
                    continue
                
                # Se passou das regras, pode comprar
                if novas_compras >= 3: break # Limite de velocidade
                
                try:
                    print(f"🎯 COMPRANDO: ${p}...")
                    client.create_and_post_order(OrderArgs(
                        price=p, size=calcular_qtd(p), side=BUY, token_id=CONFIG["TOKEN_ID"]
                    ))
                    novas_compras += 1
                    time.sleep(1) # Pausa suave
                except Exception as e:
                    print(f"   ❌ Erro Compra: {e}")

        except Exception as e:
            # Esse except pega qualquer erro dentro do ciclo e impede que o robô pare
            print(f"⚠️ ERRO NO CICLO: {e}")
        
        # Pausa final obrigatória
        time.sleep(CONFIG["INTERVALO_TEMPO"])

if __name__ == "__main__":
    main()
