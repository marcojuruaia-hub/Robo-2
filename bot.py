#!/usr/bin/env python3
"""
🤖 ROBÔ GRID V41.1 - OPERAÇÃO REAL (BLINDADO)
- Correção do erro 'NoneType' (float)
- Lógica de não repetição mantida
"""

import os
import time
import requests
import sys
# Força o log a aparecer imediatamente
sys.stdout.reconfigure(line_buffering=True)

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OpenOrderParams
from py_clob_client.order_builder.constants import BUY, SELL

print("=" * 70)
print(">>> 🤖 ROBÔ V41.1: GRID INTELIGENTE BLINDADO <<<")
print("=" * 70)

# ============================================================================
# ⚙️ CONFIGURAÇÃO
# ============================================================================
CONFIG = {
    "TOKEN_ID": "24120579393151285531790392365655515414663383379081658053153655752666989210807", 
    "PROXY": "0x658293eF9454A2DD555eb4afcE6436aDE78ab20B",
    
    # Grid: 0.64, 0.63, 0.62 ... 0.55
    "GRID_COMPRAS": [round(x * 0.01, 2) for x in range(64, 55, -1)],
    
    "LUCRO_FIXO": 0.02,           # Compra 0.64 -> Vende 0.66
    "SHARES_POR_ORDEM": 5.0,      
    "INTERVALO_TEMPO": 15,        # Tempo entre ciclos
}
DATA_API = "https://data-api.polymarket.com"
# ============================================================================

def safe_float(value):
    """Converte para float com segurança. Se for None, retorna 0.0"""
    try:
        if value is None:
            return 0.0
        return float(value)
    except:
        return 0.0

def obter_posicao_real(asset_id, user_address):
    try:
        url = f"{DATA_API}/positions"
        params = {"user": user_address, "asset_id": asset_id}
        resp = requests.get(url, params=params).json()
        if isinstance(resp, list):
            for pos in resp:
                if pos.get("asset_id") == asset_id:
                    return safe_float(pos.get("size", 0))
        return 0.0
    except: return 0.0

def calcular_qtd(preco):
    return 5.0 if preco > 0.20 else round(1.0 / preco, 2)

def main():
    key = os.getenv("PRIVATE_KEY")
    if not key:
        print("❌ ERRO: PRIVATE_KEY não configurada!")
        return
    
    try:
        client = ClobClient("https://clob.polymarket.com/", key=key, chain_id=137, signature_type=2, funder=CONFIG["PROXY"])
        client.set_api_creds(client.create_or_derive_api_creds())
        print("✅ Conectado com sucesso!")
    except Exception as e:
        print(f"❌ Falha na conexão: {e}")
        return
    
    ciclo = 0
    vendas_memoria = [] 

    while True:
        ciclo += 1
        print(f"\n🔄 CICLO {ciclo} - {time.strftime('%H:%M:%S')}")
        
        try:
            # 1. PEGAR ORDENS ABERTAS NA POLYMARKET
            todas = client.get_orders(OpenOrderParams())
            minhas = [o for o in todas if o.get('asset_id') == CONFIG["TOKEN_ID"]]
            
            # Listas de Preços já ocupados (USANDO SAFE_FLOAT PARA NÃO QUEBRAR)
            compras_abertas = []
            vendas_abertas = []
            
            for o in minhas:
                preco = safe_float(o.get('price'))
                lado = o.get('side')
                if lado == BUY:
                    compras_abertas.append(round(preco, 2))
                elif lado == SELL:
                    vendas_abertas.append(round(preco, 2))
            
            # Adiciona as vendas da memória local
            for v in vendas_memoria:
                if v not in vendas_abertas:
                    vendas_abertas.append(v)
            
            # 2. VERIFICAR CARTEIRA E CRIAR VENDAS (RECUPERAÇÃO)
            saldo = obter_posicao_real(CONFIG["TOKEN_ID"], CONFIG["PROXY"])
            
            # Soma segura das ordens de venda
            travado = sum([safe_float(o.get('size')) for o in minhas if o.get('side') == SELL])
            
            soltas = saldo - travado
            
            # Arredonda para evitar problemas de float (ex: 0.00000001)
            soltas = round(soltas, 2)
            
            print(f"📊 SALDO: {saldo} | TRAVADO: {travado} | 🟢 SOLTAS: {soltas}")
            
            if soltas >= 1.0:
                print(f"💡 DETECTADO: {soltas} shares para vender!")
                for p_compra in CONFIG["GRID_COMPRAS"]:
                    if soltas < 1.0: break
                    
                    p_venda = round(p_compra + CONFIG["LUCRO_FIXO"], 2)
                    
                    # Só vende se não tiver venda aberta nesse preço
                    if p_venda not in vendas_abertas:
                        qtd = calcular_qtd(p_compra)
                        if qtd > soltas: qtd = soltas
                        
                        try:
                            print(f"💰 VENDENDO: ${p_venda} (Lucro de ${p_compra})")
                            client.create_and_post_order(OrderArgs(
                                price=p_venda, size=qtd, side=SELL, token_id=CONFIG["TOKEN_ID"]
                            ))
                            soltas -= qtd
                            vendas_abertas.append(p_venda) 
                            vendas_memoria.append(p_venda) 
                        except Exception as e:
                            print(f"❌ Erro Venda: {e}")
            
            # Limpa memória
            if len(vendas_memoria) > 10: vendas_memoria = vendas_memoria[-10:]

            # 3. MANUTENÇÃO DO GRID (COMPRAS)
            print("🔵 VERIFICANDO GRID...")
            novas = 0
            
            for p in CONFIG["GRID_COMPRAS"]:
                p_lucro = round(p + CONFIG["LUCRO_FIXO"], 2)
                
                tem_compra = p in compras_abertas
                tem_venda_lucro = p_lucro in vendas_abertas
                
                if tem_compra:
                    # print(f"   🆗 Já tem compra a ${p}")
                    continue
