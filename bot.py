#!/usr/bin/env python3
"""
🤖 ROBÔ GRID TRADING V39 - SINCRONIZADO
Correção: Impede recompra imediata atualizando a lista de vendas em tempo real.
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
print(">>> 🤖 ROBÔ V39: ANTI-DUPLICAÇÃO ATIVADO <<<")
print("=" * 70)

# ============================================================================
# ⚙️ CONFIGURAÇÃO REAL
# ============================================================================
CONFIG = {
    "NOME": "GRID-V39-SINCRONIZADO",
    # ⚠️ ID DE HOJE (Se o mercado anterior fechou, pegue um novo!)
    "TOKEN_ID": "COLE_O_NOVO_ID_AQUI", 
    "PROXY": "0x658293eF9454A2DD555eb4afcE6436aDE78ab20B",
    
    # 🔽 ESTRATÉGIA (Ajuste conforme o preço atual)
    # Exemplo: Se preço está 0.64, operamos de 0.68 até 0.54
    # Sintaxe corrigida: range(inicio, fim, passo) com parênteses certos
    "GRID_COMPRAS": [round(x * 0.01, 2) for x in range(64, 53, -1)],
    
    # 🔽 CONFIGURAÇÕES
    "LUCRO_FIXO": 0.02,           # Lucro ajustado para $0.02
    "SHARES_POR_ORDEM": 5.0,      
    "INTERVALO_TEMPO": 30,        # Mais rápido para pegar a volatilidade
}

DATA_API = "https://data-api.polymarket.com"
# ============================================================================

def obter_posicao_real(asset_id, user_address):
    """Consulta saldo real na API de Dados"""
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
    print(f"💰 META DE LUCRO: ${CONFIG['LUCRO_FIXO']} por ordem")
    print("="*50)

    while True:
        ciclo += 1
        print(f"\n🔄 CICLO {ciclo} - {time.strftime('%H:%M:%S')}")
        
        try:
            # 1. LEITURA INICIAL
            todas_ordens = client.get_orders(OpenOrderParams())
            minhas_ordens = [o for o in todas_ordens if o.get('asset_id') == CONFIG["TOKEN_ID"]]
            
            compras_abertas = [o for o in minhas_ordens if o.get('side') == BUY]
            vendas_abertas  = [o for o in minhas_ordens if o.get('side') == SELL]
            
            precos_compras = [round(float(o.get('price')), 2) for o in compras_abertas]
            # Lista de vendas que vamos atualizar em tempo real
            precos_vendas  = [round(float(o.get('price')), 2) for o in vendas_abertas]
            
            # 2. SALDO E CÁLCULOS
            saldo_carteira = obter_posicao_real(CONFIG["TOKEN_ID"], CONFIG["PROXY"])
            saldo_em_venda = sum([float(o.get('size')) for o in vendas_abertas])
            cotas_soltas = saldo_carteira - saldo_em_venda
            
            print(f"📊 CARTEIRA: {saldo_carteira} | TRAVADO: {saldo_em_venda} | 🟢 SOLTAS: {cotas_soltas}")
            
            # ==========================================================
            # 🚀 FASE 1: CRIAR VENDAS (PRIORIDADE MÁXIMA)
            # ==========================================================
            if cotas_soltas >= 1.0:
                print(f"💡 RECUPERAÇÃO: {cotas_soltas} cotas precisam de venda...")
                
                for p_compra in CONFIG["GRID_COMPRAS"]:
                    if cotas_soltas < 1.0: break 
                    
                    p_venda_alvo = round(p_compra + CONFIG["LUCRO_FIXO"], 2)
                    
                    # Se não tem compra aberta E não tem venda aberta
                    if p_compra not in precos_compras and p_venda_alvo not in precos_vendas:
                        qtd = calcular_qtd(p_compra)
                        if qtd > cotas_soltas: qtd = cotas_soltas
                        
                        try:
                            print(f"💰 VENDENDO: ${p_venda_alvo} (Origem: ${p_compra})")
                            client.create_and_post_order(OrderArgs(
                                price=p_venda_alvo, size=qtd, side=SELL, token_id=CONFIG["TOKEN_ID"]
                            ))
                            cotas_soltas -= qtd
                            
                            # 🔥 A CORREÇÃO MÁGICA 🔥
                            # Adicionamos essa venda na lista IMEDIATAMENTE.
                            # Assim, a Fase 2 vai saber que essa venda existe e não vai recomprar.
                            precos_vendas.append(p_venda_alvo)
                            print("   ✅ Venda registrada na memória!")
                            
                        except Exception as e:
                            print(f"   ❌ Erro venda: {e}")
            
            # ==========================================================
            # 🚀 FASE 2: MANUTENÇÃO DO GRID (COMPRAS)
            # ==========================================================
            print(f"🔵 VERIFICANDO GRID...")
            novas_compras = 0
            
            for p_compra in CONFIG["GRID_COMPRAS"]:
                # Se já temos compra, ok.
                if p_compra in precos_compras: continue
                
                # Se já temos venda correspondente (MESMO QUE ACABOU DE SER CRIADA), espera.
                p_venda_corresp = round(p_compra + CONFIG["LUCRO_FIXO"], 2)
                
                if p_venda_corresp in precos_vendas:
                    # Silencioso para não poluir o log, mas eficaz
                    # print(f"   ⏳ Esperando venda a ${p_venda_corresp}...")
                    continue
                
                # Se chegou aqui: Não tem compra E não tem venda. Pode repor.
                if novas_compras >= 3: break
                
                try:
                    print(f"🎯 RECOMPRANDO: ${p_compra}...")
                    client.create_and_post_order(OrderArgs(
                        price=p_compra, size=calcular_qtd(p_compra), side=BUY, token_id=CONFIG["TOKEN_ID"]
                    ))
                    novas_compras += 1
                except Exception as e:
                    if "404" in str(e):
                        print("❌ ERRO 404: ID EXPIRADO!")
                        break
                    print(f"   ⚠️ Erro: {str(e)[:40]}")

        except Exception as e:
            print(f"❌ ERRO GERAL: {e}")
        
        time.sleep(CONFIG["INTERVALO_TEMPO"])

if __name__ == "__main__":
    main()
