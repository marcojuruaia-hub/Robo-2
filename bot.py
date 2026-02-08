#!/usr/bin/env python3
"""
🤖 ROBÔ GRID TRADING COMPLETO - BASEADO NO SEU BOT FUNCIONAL
Usa a MESMA abordagem do seu bot de vendas que funciona!
"""

import os
import time
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY, SELL

print("=" * 70)
print(">>> 🤖 ROBÔ GRID TRADING - VERSÃO FUNCIONAL <<<")
print("=" * 70)

# ============================================================================
# ⚙️ CONFIGURAÇÃO IDÊNTICA AO SEU BOT QUE FUNCIONA
# ============================================================================
CONFIG = {
    "NOME": "GRID-AUTO-C/V",
    "TOKEN_ID": "85080102177445047827595824773776292884437000821375292353013080455752528630674",
    "PROXY": "0x658293eF9454A2DD555eb4afcE6436aDE78ab20B",
    
    # 🔽 ESTRATÉGIA DE COMPRA
    "COMPRA_INICIO": 0.80,      # Começa comprando a 0.80
    "COMPRA_FIM": 0.50,         # Até 0.50
    "INTERVALO_COMPRA": 0.02,   # Espaço entre ordens de compra
    
    # 🔽 ESTRATÉGIA DE VENDA
    "LUCRO_POR_OPERACAO": 0.05, # Vende com +$0.05 de lucro
    
    # 🔽 CONFIGURAÇÕES OPERACIONAIS
    "SHARES_POR_ORDEM": 5,      # ⚠️ COMECE COM 1!
    "INTERVALO_TEMPO": 30,      # Segundos entre ciclos
    "MAX_ORDENS": 10,           # Máximo de ordens simultâneas
}
# ============================================================================

def criar_grid_compras(config):
    """Cria grid de preços para compra"""
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
    """Calcula preço de venda com lucro"""
    lucro = config["LUCRO_POR_OPERACAO"]
    return round(preco_compra + lucro, 2)

def main():
    # 1. Criar grid
    CONFIG["GRID_COMPRAS"] = criar_grid_compras(CONFIG)
    
    print(f"🔧 CONFIGURAÇÃO:")
    print(f"   Nome: {CONFIG['NOME']}")
    print(f"   Grid: {len(CONFIG['GRID_COMPRAS'])} preços")
    print(f"   Compra: ${CONFIG['COMPRA_INICIO']} até ${CONFIG['COMPRA_FIM']}")
    print(f"   Lucro: ${CONFIG['LUCRO_POR_OPERACAO']} por share")
    print(f"   Intervalo: {CONFIG['INTERVALO_TEMPO']}s")
    print("-" * 50)
    
    # 2. Conectar (MESMO MÉTODO DO SEU BOT QUE FUNCIONA)
    key = os.getenv("PRIVATE_KEY")
    if not key:
        print("❌ ERRO: PRIVATE_KEY não configurada!")
        print("   Railway: Variables → PRIVATE_KEY=sua_chave")
        return
    
    try:
        # ⭐⭐ MESMA CONEXÃO DO SEU BOT QUE FUNCIONA ⭐⭐
        client = ClobClient(
            "https://clob.polymarket.com/",  # ⚠️ MAINNET, não testnet!
            key=key,
            chain_id=137,  # Polygon Mainnet
            signature_type=2,
            funder=CONFIG["PROXY"]
        )
        client.set_api_creds(client.create_or_derive_api_creds())
        print("✅ Conectado ao Polymarket MAINNET!")
        print(f"✅ API Credentials derivadas da private key")
    except Exception as e:
        print(f"❌ Falha na conexão: {e}")
        return
    
    # 3. Controle interno
    ciclo = 0
    ordens_compra_ativas = {}  # {preco: order_id}
    ordens_venda_ativas = {}   # {preco_compra: order_id_venda}
    posicoes_compradas = []    # Compra executadas aguardando venda
    
    try:
        while True:
            ciclo += 1
            
            print(f"\n{'='*60}")
            print(f"🔄 CICLO {ciclo} - {time.strftime('%H:%M:%S')}")
            print(f"{'='*60}")
            
            # 4. Verificar ordens atuais
            ordens_ativas = []
            try:
                todas_ordens = client.get_orders()
                for ordem in todas_ordens:
                    ordem_dict = ordem.__dict__ if hasattr(ordem, '__dict__') else dict(ordem)
                    
                    if ordem_dict.get('token_id') == CONFIG["TOKEN_ID"]:
                        ordens_ativas.append({
                            'id': ordem_dict.get('id', ''),
                            'price': float(ordem_dict.get('price', 0)),
                            'side': ordem_dict.get('side', '').lower(),
                            'status': ordem_dict.get('status', 'open')
                        })
                
                print(f"📊 Ordens ativas: {len(ordens_ativas)}")
            except Exception as e:
                print(f"⚠️  Erro ao ver ordens: {e}")
                ordens_ativas = []
            
            # 5. Atualizar controle interno
            ordens_compra_ativas.clear()
            ordens_venda_ativas.clear()
            
            for ordem in ordens_ativas:
                preco = ordem['price']
                
                if ordem['side'] == 'buy':
                    ordens_compra_ativas[preco] = ordem['id']
                elif ordem['side'] == 'sell':
                    # Procurar qual compra corresponde
                    for compra in posicoes_compradas:
                        if calcular_preco_venda(compra, CONFIG) == preco:
                            ordens_venda_ativas[compra] = ordem['id']
            
            # 6. Verificar se alguma compra foi executada
            for ordem in ordens_ativas:
                if ordem['side'] == 'buy' and ordem.get('status') == 'filled':
                    preco_compra = ordem['price']
                    
                    if preco_compra not in posicoes_compradas and preco_compra not in ordens_venda_ativas:
                        print(f"🎯 COMPRA EXECUTADA detectada @ ${preco_compra:.2f}")
                        
                        # Criar ordem de venda
                        preco_venda = calcular_preco_venda(preco_compra, CONFIG)
                        quantidade = CONFIG["SHARES_POR_ORDEM"]
                        
                        try:
                            ordem_venda = OrderArgs(
                                price=preco_venda,
                                size=quantidade,
                                side=SELL,
                                token_id=CONFIG["TOKEN_ID"]
                            )
                            
                            client.create_and_post_order(ordem_venda)
                            posicoes_compradas.append(preco_compra)
                            
                            lucro = CONFIG["LUCRO_POR_OPERACAO"] * quantidade
                            print(f"💰 VENDA criada: {quantidade} @ ${preco_venda:.2f}")
                            print(f"   📈 Lucro potencial: ${lucro:.2f}")
                            
                        except Exception as e:
                            print(f"⚠️  Erro na venda @ ${preco_venda:.2f}: {e}")
            
            # 7. Criar novas ordens de compra (grid)
            print(f"\n🔵 CRIANDO ORDENS DE COMPRA...")
            ordens_novas = 0
            
            for preco in CONFIG["GRID_COMPRAS"]:
                # Limite máximo
                if len(ordens_compra_ativas) >= CONFIG["MAX_ORDENS"]:
                    print(f"⚠️  Limite de {CONFIG['MAX_ORDENS']} ordens atingido")
                    break
                
                # Se já tem ordem neste preço, pular
                if preco in ordens_compra_ativas:
                    continue
                
                # Tentar criar ordem
                print(f"🎯 Tentando COMPRA a ${preco:.2f}...")
                quantidade = CONFIG["SHARES_POR_ORDEM"]
                
                try:
                    ordem_compra = OrderArgs(
                        price=preco,
                        size=quantidade,
                        side=BUY,
                        token_id=CONFIG["TOKEN_ID"]
                    )
                    
                    client.create_and_post_order(ordem_compra)
                    ordens_compra_ativas[preco] = "new"
                    ordens_novas += 1
                    
                    print(f"✅ COMPRA criada: {quantidade} @ ${preco:.2f}")
                    
                    # Pausa para evitar rate limit
                    time.sleep(1)
                    
                    # Máximo 2 ordens novas por ciclo
                    if ordens_novas >= 2:
                        break
                        
                except Exception as e:
                    erro = str(e).lower()
                    if "balance" in erro or "insufficient" in erro:
                        print(f"💰 Sem saldo para ${preco:.2f}")
                        break
                    elif "already" in erro or "duplicate" in erro:
                        print(f"⏭️  Já existe ordem a ${preco:.2f}")
                        ordens_compra_ativas[preco] = "existing"
                    else:
                        print(f"⚠️  Erro: {e}")
            
            # 8. Resumo do ciclo
            print(f"\n📋 RESUMO DO CICLO {ciclo}:")
            print(f"   • Ordens de compra ativas: {len(ordens_compra_ativas)}")
            print(f"   • Ordens de venda ativas: {len(ordens_venda_ativas)}")
            print(f"   • Posições compradas: {len(posicoes_compradas)}")
            print(f"   • Novas ordens criadas: {ordens_novas}")
            
            # Mostrar preços ativos
            if ordens_compra_ativas:
                precos = sorted(ordens_compra_ativas.keys(), reverse=True)
                print(f"\n🛒 COMPRAS PENDENTES (top 3):")
                for preco in precos[:3]:
                    print(f"   • ${preco:.2f}")
            
            if ordens_venda_ativas:
                print(f"\n💰 VENDAS PENDENTES (top 3):")
                for compra in list(ordens_venda_ativas.keys())[:3]:
                    venda = calcular_preco_venda(compra, CONFIG)
                    lucro = CONFIG["LUCRO_POR_OPERACAO"]
                    print(f"   • Compra: ${compra:.2f} → Venda: ${venda:.2f} (+${lucro:.2f})")
            
            # 9. Aguardar próximo ciclo
            print(f"\n⏳ Próximo ciclo em {CONFIG['INTERVALO_TEMPO']} segundos...")
            print(f"{'='*60}")
            time.sleep(CONFIG["INTERVALO_TEMPO"])
            
    except KeyboardInterrupt:
        print(f"\n\n🛑 Robô parado pelo usuário")
        print(f"   Total ciclos: {ciclo}")
        print(f"   Posições: {len(posicoes_compradas)}")
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
