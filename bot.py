#!/usr/bin/env python3
"""
🤖 ROBÔ GRID TRADING V38 - MESTRE DA RECONCILIAÇÃO
Corrige o erro de "Status Desconhecido" lendo a API de Dados Real.
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
print(">>> 🤖 ROBÔ V38: RECONCILIAÇÃO DE SALDO ATIVADA <<<")
print("=" * 70)

# ============================================================================
# ⚙️ CONFIGURAÇÃO REAL
# ============================================================================
CONFIG = {
    "NOME": "GRID-RECONCILIACAO-V38",
    # ⚠️ MUITO IMPORTANTE: Garanta que este ID é válido para HOJE!
    "TOKEN_ID": "24120579393151285531790392365655515414663383379081658053153655752666989210807", 
    "PROXY": "0x658293eF9454A2DD555eb4afcE6436aDE78ab20B",
    
    # 🔽 ESTRATÉGIA
    # Exemplo: Se preço atual é 0.60, grid de 0.68 a 0.54
    "GRID_COMPRAS": [round(x * 0.01, 2) for x in range(65, 50, -1],
    
    # 🔽 CONFIGURAÇÕES
    "LUCRO_FIXO": 0.02,           # Lucro desejado por share
    "SHARES_POR_ORDEM": 5.0,      # Quantidade fixa (ajustável)
    "INTERVALO_TEMPO": 20,        # Ciclos mais rápidos (30s)
}

DATA_API = "https://data-api.polymarket.com"
# ============================================================================

def obter_posicao_real(asset_id, user_address):
    """Consulta a API de Dados para saber o saldo REAL na carteira"""
    try:
        url = f"{DATA_API}/positions"
        params = {"user": user_address, "asset_id": asset_id}
        resp = requests.get(url, params=params).json()
        for pos in resp:
            if pos.get("asset_id") == asset_id:
                return float(pos.get("size", 0))
        return 0.0
    except Exception as e:
        print(f"⚠️ Erro na API de Dados: {e}")
        return 0.0

def calcular_qtd(preco):
    # Regra inteligente: 5 shares ou valor > $1
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
    print("\n" + "="*50)
    print(f"🚀 INICIANDO GRID: {CONFIG['GRID_COMPRAS']}")
    print("="*50)

    while True:
        ciclo += 1
        print(f"\n🔄 CICLO {ciclo} - {time.strftime('%H:%M:%S')}")
        
        try:
            # 1. LEITURA DO ESTADO ATUAL (SNAPSHOT)
            todas_ordens = client.get_orders(OpenOrderParams())
            
            # Filtra apenas ordens deste mercado
            minhas_ordens = [o for o in todas_ordens if o.get('asset_id') == CONFIG["TOKEN_ID"]]
            
            compras_abertas = [o for o in minhas_ordens if o.get('side') == BUY]
            vendas_abertas  = [o for o in minhas_ordens if o.get('side') == SELL]
            
            precos_compras = [round(float(o.get('price')), 2) for o in compras_abertas]
            precos_vendas  = [round(float(o.get('price')), 2) for o in vendas_abertas]
            
            # 2. LEITURA DA CARTEIRA (A VERDADE ABSOLUTA)
            saldo_carteira = obter_posicao_real(CONFIG["TOKEN_ID"], CONFIG["PROXY"])
            
            # Calcula quantas cotas já estão 'travadas' em ordens de venda
            saldo_em_venda = sum([float(o.get('size')) for o in vendas_abertas])
            
            # Cotas Soltas = Saldo Real - Saldo Comprometido em Vendas
            # Se isso for positivo, significa que uma compra foi executada e precisamos vender!
            cotas_soltas = saldo_carteira - saldo_em_venda
            
            print(f"📊 SALDO REAL: {saldo_carteira} | EM VENDA: {saldo_em_venda} | 🟢 SOLTAS: {cotas_soltas}")
            
            # ==========================================================
            # 🚀 FASE 1: CRIAR VENDAS (RECUPERAÇÃO)
            # ==========================================================
            if cotas_soltas >= 1.0: # Se tiver pelo menos 1 cota solta
                print(f"💡 DETECTADO: {cotas_soltas} cotas sem venda! Iniciando criação de ordens...")
                
                # Vamos tentar casar essas cotas soltas com nosso Grid
                # Prioridade: Vender para as compras mais caras primeiro (para garantir lucro logo)
                for p_compra in CONFIG["GRID_COMPRAS"]:
                    if cotas_soltas < 1.0: break 
                    
                    # Se NÃO tem compra aberta neste preço, e NÃO tem venda aberta no alvo...
                    # É muito provável que esta seja a compra que foi executada.
                    p_venda_alvo = round(p_compra + CONFIG["LUCRO_FIXO"], 2)
                    
                    if p_compra not in precos_compras and p_venda_alvo not in precos_vendas:
                        qtd = calcular_qtd(p_compra)
                        
                        # Ajusta qtd se o saldo solto for menor que o lote padrão
                        if qtd > cotas_soltas: qtd = cotas_soltas
                        
                        try:
                            print(f"💰 CRIANDO VENDA: ${p_venda_alvo} (Ref: Compra ${p_compra})")
                            client.create_and_post_order(OrderArgs(
                                price=p_venda_alvo, 
                                size=qtd, 
                                side=SELL, 
                                token_id=CONFIG["TOKEN_ID"]
                            ))
                            cotas_soltas -= qtd
                            print("   ✅ Venda criada com sucesso!")
                        except Exception as e:
                            print(f"   ❌ Erro ao criar venda: {e}")
            
            # ==========================================================
            # 🚀 FASE 2: MANUTENÇÃO DO GRID (COMPRAS)
            # ==========================================================
            print(f"🔵 VERIFICANDO GRID DE COMPRAS...")
            novas_compras = 0
            
            for p_compra in CONFIG["GRID_COMPRAS"]:
                # Se já temos compra aberta, pula
                if p_compra in precos_compras:
                    continue
                
                # Se já temos venda aberta correspondente (lucro esperando), NÃO recompra ainda
                p_venda_corresp = round(p_compra + CONFIG["LUCRO_FIXO"], 2)
                if p_venda_corresp in precos_vendas:
                    print(f"   ⏳ ${p_compra}: Aguardando venda a ${p_venda_corresp} ser executada...")
                    continue
                
                # Se chegamos aqui: Não tem compra, não tem venda. O caminho está livre.
                if novas_compras >= 3: break # Limite de velocidade
                
                try:
                    print(f"🎯 Recolocando COMPRA a ${p_compra}...")
                    client.create_and_post_order(OrderArgs(
                        price=p_compra, 
                        size=calcular_qtd(p_compra), 
                        side=BUY, 
                        token_id=CONFIG["TOKEN_ID"]
                    ))
                    print("   ✅ Ordem enviada!")
                    novas_compras += 1
                except Exception as e:
                    erro = str(e)
                    if "404" in erro:
                        print("❌ ERRO 404: ID EXPIRADO! Pare o robô e troque o ID.")
                        break
                    elif "balance" in erro.lower():
                        print(f"   💰 Sem saldo USDC para ${p_compra}")
                    else:
                        print(f"   ⚠️ Erro menor: {erro[:50]}")

        except Exception as e:
            print(f"❌ ERRO GERAL NO CICLO: {e}")
        
        print(f"⏳ Aguardando {CONFIG['INTERVALO_TEMPO']}s...")
        time.sleep(CONFIG["INTERVALO_TEMPO"])

if __name__ == "__main__":
    main()
