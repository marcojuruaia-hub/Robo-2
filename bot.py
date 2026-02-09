#!/usr/bin/env python3
"""
🤖 ROBÔ GRID V41 - OPERAÇÃO REAL (CORRIGIDO)
- ID Confirmado
- Sem repetição de ordens
- Lógica: Compra -> Executa -> Vende -> Executa -> Recompra
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
print(">>> 🤖 ROBÔ V41: GRID INTELIGENTE ATIVADO <<<")
print("=" * 70)

# ============================================================================
# ⚙️ CONFIGURAÇÃO
# ============================================================================
CONFIG = {
    "TOKEN_ID": "24120579393151285531790392365655515414663383379081658053153655752666989210807", 
    "PROXY": "0x658293eF9454A2DD555eb4afcE6436aDE78ab20B",
    
    # Grid: 0.64, 0.63, 0.62 ... 0.56
    "GRID_COMPRAS": [round(x * 0.01, 2) for x in range(64, 55, -1)],
    
    "LUCRO_FIXO": 0.02,           # Compra 0.64 -> Vende 0.66
    "SHARES_POR_ORDEM": 5.0,      
    "INTERVALO_TEMPO": 15,        # Tempo entre ciclos
}
DATA_API = "https://data-api.polymarket.com"
# ============================================================================

def obter_posicao_real(asset_id, user_address):
    try:
        url = f"{DATA_API}/positions"
        params = {"user": user_address, "asset_id": asset_id}
        resp = requests.get(url, params=params).json()
        for pos in resp:
            if pos.get("asset_id") == asset_id:
                return float(pos.get("size", 0))
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
    # Memória local para evitar recompra imediata antes da API atualizar
    vendas_memoria = [] 

    while True:
        ciclo += 1
        print(f"\n🔄 CICLO {ciclo} - {time.strftime('%H:%M:%S')}")
        
        try:
            # 1. PEGAR ORDENS ABERTAS NA POLYMARKET
            todas = client.get_orders(OpenOrderParams())
            minhas = [o for o in todas if o.get('asset_id') == CONFIG["TOKEN_ID"]]
            
            # Listas de Preços já ocupados
            compras_abertas = [round(float(o.get('price')), 2) for o in minhas if o.get('side') == BUY]
            vendas_abertas  = [round(float(o.get('price')), 2) for o in minhas if o.get('side') == SELL]
            
            # Adiciona as vendas da memória local para segurança extra
            for v in vendas_memoria:
                if v not in vendas_abertas:
                    vendas_abertas.append(v)
            
            # 2. VERIFICAR CARTEIRA E CRIAR VENDAS (RECUPERAÇÃO)
            saldo = obter_posicao_real(CONFIG["TOKEN_ID"], CONFIG["PROXY"])
            travado = sum([float(o.get('size')) for o in minhas if o.get('side') == SELL])
            soltas = saldo - travado
            
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
                            vendas_abertas.append(p_venda) # Atualiza lista local
                            vendas_memoria.append(p_venda) # Salva na memória
                        except Exception as e:
                            print(f"❌ Erro Venda: {e}")
            
            # Limpa memória de vendas antigas (mantém apenas as últimas 10 para não crescer infinito)
            if len(vendas_memoria) > 10: vendas_memoria = vendas_memoria[-10:]

            # 3. MANUTENÇÃO DO GRID (COMPRAS)
            print("🔵 VERIFICANDO GRID...")
            novas = 0
            
            for p in CONFIG["GRID_COMPRAS"]:
                # REGRA DE OURO: Só compra se NÃO tem compra E NÃO tem venda (lucro esperando)
                p_lucro = round(p + CONFIG["LUCRO_FIXO"], 2)
                
                tem_compra = p in compras_abertas
                tem_venda_lucro = p_lucro in vendas_abertas
                
                if tem_compra:
                    # print(f"   🆗 Já tem compra a ${p}")
                    continue
                
                if tem_venda_lucro:
                    print(f"   ⏳ PULA ${p}: Aguardando venda a ${p_lucro} executar.")
                    continue
                
                # Se chegou aqui, o nível está vazio. Pode comprar.
                if novas >= 3: break # Limite de velocidade
                
                try:
                    print(f"🎯 ENVIANDO COMPRA: ${p}...")
                    client.create_and_post_order(OrderArgs(
                        price=p, size=calcular_qtd(p), side=BUY, token_id=CONFIG["TOKEN_ID"]
                    ))
                    novas += 1
                    # Pequena pausa para a API respirar
                    time.sleep(1)
                except Exception as e:
                    print(f"   ❌ Erro Compra: {e}")

        except Exception as e:
            print(f"❌ ERRO GERAL: {e}")
        
        time.sleep(CONFIG["INTERVALO_TEMPO"])

if __name__ == "__main__":
    main()
