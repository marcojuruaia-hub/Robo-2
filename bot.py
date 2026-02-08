#!/usr/bin/env python3
"""
🤖 ROBÔ GRID TRADING - VERSÃO CORRIGIDA (VÊ ORDENS)
"""

import os
import time
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY, SELL

print("=" * 70)
print(">>> 🤖 ROBÔ GRID TRADING - VÊ ORDENS CORRETAMENTE <<<")
print("=" * 70)

# ============================================================================
CONFIG = {
    "NOME": "GRID-CORRIGIDO",
    "TOKEN_ID": "85080102177445047827595824773776292884437000821375292353013080455752528630674",
    "PROXY": "0x658293eF9454A2DD555eb4afcE6436aDE78ab20B",
    
    "COMPRA_INICIO": 0.80,
    "COMPRA_FIM": 0.50,
    "INTERVALO_COMPRA": 0.02,
    "LUCRO_POR_OPERACAO": 0.05,
    
    "SHARES_POR_ORDEM": 1,      # ⚠️ MUDE PARA 1!
    "INTERVALO_TEMPO": 30,
    "MAX_ORDENS": 10,
}
# ============================================================================

def criar_grid_compras(config):
    inicio = config["COMPRA_INICIO"]
    fim = config["COMPRA_FIM"]
    intervalo = config["INTERVALO_COMPRA"]
    
    preco_atual = inicio
    grid = []
    while preco_atual >= fim:
        grid.append(round(preco_atual, 2))
        preco_atual -= intervalo
    
    return grid

def calcular_preco_venda(preco_compra, config):
    return round(preco_compra + config["LUCRO_POR_OPERACAO"], 2)

def main():
    CONFIG["GRID_COMPRAS"] = criar_grid_compras(CONFIG)
    
    print(f"🔧 CONFIGURAÇÃO:")
    print(f"   Token ID: {CONFIG['TOKEN_ID'][:20]}...")
    print(f"   Grid: {len(CONFIG['GRID_COMPRAS'])} preços")
    print("-" * 50)
    
    # CONEXÃO (igual ao seu bot funcional)
    key = os.getenv("PRIVATE_KEY")
    if not key:
        print("❌ ERRO: PRIVATE_KEY não configurada!")
        return
    
    try:
        client = ClobClient(
            "https://clob.polymarket.com/",
            key=key,
            chain_id=137,
            signature_type=2,
            funder=CONFIG["PROXY"]
        )
        client.set_api_creds(client.create_or_derive_api_creds())
        print("✅ Conectado e API Creds derivadas")
    except Exception as e:
        print(f"❌ Falha na conexão: {e}")
        return
    
    # CONTROLE INTERNO FORTE
    ciclo = 0
    ordens_criadas_interno = []  # O que NÓS criamos
    posicoes_compradas = []
    
    try:
        while True:
            ciclo += 1
            
            print(f"\n{'='*60}")
            print(f"🔄 CICLO {ciclo} - {time.strftime('%H:%M:%S')}")
            print(f"{'='*60}")
            
            # ========== PASSO 1: VER ORDENS NA API (CORRETAMENTE) ==========
            ordens_api_compras = []
            ordens_api_vendas = []
            
            try:
                # DEBUG: Ver o que a API retorna
                todas_raw = client.get_orders()
                print(f"🔍 API retornou {len(todas_raw)} ordens totais")
                
                for ordem in todas_raw:
                    try:
                        # Converter para dict de forma segura
                        if hasattr(ordem, '__dict__'):
                            o = ordem.__dict__
                        else:
                            o = dict(ordem)
                        
                        # Verificar se é do nosso token
                        token = o.get('token_id', o.get('asset_id', ''))
                        if token == CONFIG["TOKEN_ID"]:
                            preco = float(o.get('price', 0))
                            lado = o.get('side', '').lower()
                            status = o.get('status', 'open')
                            
                            if lado == 'buy':
                                ordens_api_compras.append({
                                    'preco': preco,
                                    'status': status
                                })
                            elif lado == 'sell':
                                ordens_api_vendas.append({
                                    'preco': preco,
                                    'status': status
                                })
                    except:
                        continue
                
                print(f"📊 API: {len(ordens_api_compras)} compras, {len(ordens_api_vendas)} vendas")
                
            except Exception as e:
                print(f"⚠️  Erro ao ver ordens API: {e}")
            
            # ========== PASSO 2: CRIAR NOVAS ORDENS ==========
            print(f"\n🔵 ANALISANDO GRID...")
            novas_criadas = 0
            
            for preco in CONFIG["GRID_COMPRAS"]:
                # Limite máximo
                if len(ordens_criadas_interno) >= CONFIG["MAX_ORDENS"]:
                    print(f"⚠️  Limite de {CONFIG['MAX_ORDENS']} ordens")
                    break
                
                # Verificar se JÁ TEMOS no controle interno
                if preco in ordens_criadas_interno:
                    print(f"⏭️  ${preco:.2f}: Já criamos (controle interno)")
                    continue
                
                # Verificar se JÁ EXISTE na API
                ja_existe_api = any(
                    abs(o['preco'] - preco) < 0.001 
                    for o in ordens_api_compras
                )
                
                if ja_existe_api:
                    print(f"⏭️  ${preco:.2f}: Já existe na API")
                    ordens_criadas_interno.append(preco)
                    continue
                
                # Tentar criar
                print(f"🎯 Tentando COMPRA a ${preco:.2f}...")
                quantidade = CONFIG["SHARES_POR_ORDEM"]
                
                try:
                    ordem = OrderArgs(
                        price=preco,
                        size=quantidade,
                        side=BUY,
                        token_id=CONFIG["TOKEN_ID"]
                    )
                    
                    resultado = client.create_and_post_order(ordem)
                    
                    if resultado:
                        ordens_criadas_interno.append(preco)
                        novas_criadas += 1
                        print(f"✅ COMPRA criada: {quantidade} @ ${preco:.2f}")
                        
                        # Pausa e limite
                        time.sleep(2)
                        if novas_criadas >= 2:
                            break
                    
                except Exception as e:
                    erro = str(e).lower()
                    if "balance" in erro or "insufficient" in erro:
                        print(f"💰 Sem saldo para ${preco:.2f}")
                        break
                    elif "already" in erro or "duplicate" in erro:
                        print(f"⏭️  ${preco:.2f}: Já existe (erro API)")
                        ordens_criadas_interno.append(preco)
                    else:
                        print(f"⚠️  Erro: {str(e)[:50]}...")
            
            # ========== PASSO 3: RESUMO ==========
            print(f"\n📋 RESUMO CICLO {ciclo}:")
            print(f"   • Controle interno: {len(ordens_criadas_interno)} ordens")
            print(f"   • API compras: {len(ordens_api_compras)} ordens")
            print(f"   • Novas criadas: {novas_criadas}")
            
            if ordens_criadas_interno:
                print(f"\n🎯 NOSSAS ORDENS:")
                for preco in sorted(ordens_criadas_interno, reverse=True)[:5]:
                    print(f"   • ${preco:.2f}")
            
            # ========== PASSO 4: AGUARDAR ==========
            print(f"\n⏳ Próximo ciclo em {CONFIG['INTERVALO_TEMPO']}s...")
            print(f"{'='*60}")
            time.sleep(CONFIG["INTERVALO_TEMPO"])
            
    except KeyboardInterrupt:
        print(f"\n\n🛑 Robô parado")
        print(f"   Ciclos: {ciclo}")
        print(f"   Ordens criadas: {len(ordens_criadas_interno)}")
    except Exception as e:
        print(f"\n❌ ERRO: {e}")

if __name__ == "__main__":
    main()
