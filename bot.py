#!/usr/bin/env python3
"""
🤖 ROBÔ GRID TRADING COMPLETO - COMPRA E VENDA AUTOMÁTICA
Polymarket | Railway | Sem duplicação
"""

import os
import time
import asyncio
from decimal import Decimal
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY, SELL
from py_clob_client.constants import POLYGON
from eth_account import Account

print("=" * 70)
print(">>> 🤖 ROBÔ GRID TRADING - COMPRA E VENDA AUTOMÁTICA <<<")
print("=" * 70)

# ============================================================================
# ⚙️ CONFIGURAÇÃO FÁCIL (EDITA SÓ AQUI!)
# ============================================================================
CONFIG = {
    # 🔐 SUA CHAVE PRIVADA (Railway Variables)
    "PRIVATE_KEY": os.getenv("PRIVATE_KEY", ""),
    
    # 🌐 REDE (True = Testnet, False = Mainnet)
    "TESTNET": True,  # ⚠️ DEIXE TRUE PARA TESTES!
    
    # 📊 MERCADO (SEU TOKEN ID)
    "TOKEN_ID": "85080102177445047827595824773776292884437000821375292353013080455752528630674",
    
    # 🎯 ESTRATÉGIA DE COMPRA
    "COMPRA_INICIO": 0.90,     # Começa comprando a $0.80
    "COMPRA_FIM": 0.50,        # Para de comprar em $0.50
    "INTERVALO_COMPRA": 0.02,  # Espaço entre ordens de compra
    
    # 💰 ESTRATÉGIA DE VENDA (LUCRO AUTOMÁTICO)
    "LUCRO_POR_OPERACAO": 0.05,  # Vende com $0.05 de lucro por share
    
    # ⚙️ CONFIGURAÇÕES OPERACIONAIS
    "SHARES_POR_ORDEM": 5,     # ⚠️ COMECE COM 1 SHARE!
    "INTERVALO_CICLO": 30,     # Segundos entre verificações
    "MAX_ORDENS_ABERTAS": 10,  # Máximo de ordens simultâneas
}
# ============================================================================

class RoboGridCompleto:
    def __init__(self, config):
        self.config = config
        
        # Verificar chave privada
        if not config["PRIVATE_KEY"]:
            raise ValueError("❌ ERRO: PRIVATE_KEY não configurada!")
        
        # Configurar rede
        self.testnet = config["TESTNET"]
        host = "https://clob-testnet.polymarket.com" if self.testnet else "https://clob.polymarket.com"
        chain_id = 80001 if self.testnet else 137
        
        # Criar conta e cliente
        self.account = Account.from_key(config["PRIVATE_KEY"])
        self.client = ClobClient(
            host=host,
            key=self.account.key,
            chain_id=chain_id,
            signature_type=POLYGON,
        )
        
        # Configurar credenciais API
        try:
            self.client.set_api_creds(self.client.create_or_derive_api_creds())
        except:
            print("⚠️  API Credentials não configuradas (pode precisar)")
        
        # Gerar grid de compras
        self.grid_compras = self._gerar_grid_compras()
        
        # Controle interno
        self.ordens_compra_ativas = {}  # {preco: order_id}
        self.ordens_venda_ativas = {}   # {preco_compra: order_id_venda}
        self.posicoes_compradas = []    # Lista de compras executadas
        self.ciclo_numero = 0
        
        print(f"✅ Conta: {self.account.address[:10]}...")
        print(f"✅ Rede: {'TESTNET' if self.testnet else 'MAINNET'}")
        print(f"✅ Grid: {len(self.grid_compras)} níveis de compra")
        print(f"✅ Lucro alvo: ${config['LUCRO_POR_OPERACAO']} por operação")
    
    def _gerar_grid_compras(self):
        """Gera grid de preços para compra"""
        inicio = self.config["COMPRA_INICIO"]
        fim = self.config["COMPRA_FIM"]
        intervalo = self.config["INTERVALO_COMPRA"]
        
        precos = []
        preco_atual = inicio
        while preco_atual >= fim:
            precos.append(round(preco_atual, 2))
            preco_atual -= intervalo
        
        return precos
    
    def _calcular_preco_venda(self, preco_compra):
        """Calcula preço de venda com lucro"""
        lucro = self.config["LUCRO_POR_OPERACAO"]
        return round(preco_compra + lucro, 2)
    
    async def _obter_ordens_abertas(self):
        """Obtém todas as ordens abertas da conta"""
        try:
            # Método mais simples para evitar erros de API
            # Tentamos obter ordens de forma genérica
            ordens = await self.client.get_orders()
            
            nossas_ordens = []
            for ordem in ordens:
                # Verificar de forma segura se é nossa ordem
                try:
                    ordem_dict = ordem.__dict__ if hasattr(ordem, '__dict__') else dict(ordem)
                    
                    # Verificar trader/maker
                    trader = ordem_dict.get('trader') or ordem_dict.get('maker')
                    if trader and trader.lower() == self.account.address.lower():
                        nossas_ordens.append({
                            'id': ordem_dict.get('id', ''),
                            'price': float(ordem_dict.get('price', 0)),
                            'side': ordem_dict.get('side', '').lower(),
                            'token_id': ordem_dict.get('token_id', ''),
                            'status': ordem_dict.get('status', 'open')
                        })
                except:
                    continue
            
            return nossas_ordens
            
        except Exception as e:
            print(f"⚠️  Erro ao obter ordens: {e}")
            return []
    
    async def _cancelar_todas_ordens(self):
        """Cancela TODAS as ordens abertas para começar do zero"""
        print("\n🔄 CANCELANDO TODAS AS ORDENS EXISTENTES...")
        
        ordens = await self._obter_ordens_abertas()
        if not ordens:
            print("✅ Nenhuma ordem para cancelar")
            return
        
        print(f"📋 Encontradas {len(ordens)} ordens para cancelar")
        
        canceladas = 0
        for ordem in ordens:
            try:
                await self.client.cancel_order(ordem['id'])
                print(f"   ✅ Cancelada ordem {ordem['side']} @ ${ordem['price']:.2f}")
                canceladas += 1
                time.sleep(0.5)  # Pausa para evitar rate limit
            except:
                print(f"   ❌ Falha ao cancelar ordem")
        
        print(f"✅ Total canceladas: {canceladas}/{len(ordens)}")
        
        # Limpar controle interno
        self.ordens_compra_ativas.clear()
        self.ordens_venda_ativas.clear()
    
    async def _verificar_ordens_executadas(self):
        """Verifica se alguma ordem de compra foi executada e cria venda"""
        ordens = await self._obter_ordens_abertas()
        
        # Filtrar apenas ordens de compra executadas
        for ordem in ordens:
            if ordem['side'] == 'buy' and ordem.get('status') == 'filled':
                preco_compra = ordem['price']
                
                # Verificar se já criamos venda para esta compra
                if preco_compra not in self.ordens_venda_ativas and preco_compra not in self.posicoes_compradas:
                    print(f"🎯 COMPRA EXECUTADA detectada @ ${preco_compra:.2f}")
                    
                    # Calcular preço de venda com lucro
                    preco_venda = self._calcular_preco_venda(preco_compra)
                    
                    # Criar ordem de venda
                    await self._criar_ordem_venda(preco_venda, preco_compra)
                    
                    # Registrar como posição comprada
                    self.posicoes_compradas.append(preco_compra)
    
    async def _criar_ordem_compra(self, preco):
        """Cria ordem de compra se não existir"""
        try:
            # Verificar se já temos ordem neste preço
            if preco in self.ordens_compra_ativas:
                return False
            
            # Verificar limite de ordens
            if len(self.ordens_compra_ativas) >= self.config["MAX_ORDENS_ABERTAS"]:
                return False
            
            # Criar ordem
            quantidade = self.config["SHARES_POR_ORDEM"]
            price_decimal = Decimal(str(preco))
            
            order_args = OrderArgs(
                price=price_decimal,
                size=str(quantidade),
                side=BUY,
                token_id=self.config["TOKEN_ID"],
            )
            
            # Enviar ordem
            resultado = await self.client.create_order(order_args)
            
            if resultado:
                # Extrair ID da ordem
                ordem_id = ""
                if hasattr(resultado, 'id'):
                    ordem_id = resultado.id
                elif isinstance(resultado, dict):
                    ordem_id = resultado.get('id', '')
                
                if ordem_id:
                    self.ordens_compra_ativas[preco] = ordem_id
                    print(f"✅ COMPRA criada: {quantidade} share(s) @ ${preco:.2f}")
                    return True
            
            return False
            
        except Exception as e:
            erro_msg = str(e).lower()
            if "insufficient" in erro_msg or "balance" in erro_msg:
                print(f"💰 Sem saldo para ordem @ ${preco:.2f}")
            elif "already" in erro_msg or "duplicate" in erro_msg:
                print(f"⏭️  Já existe ordem @ ${preco:.2f}")
                self.ordens_compra_ativas[preco] = "duplicate"
            else:
                print(f"⚠️  Erro na compra @ ${preco:.2f}: {str(e)[:50]}...")
            return False
    
    async def _criar_ordem_venda(self, preco_venda, preco_compra):
        """Cria ordem de venda com lucro"""
        try:
            quantidade = self.config["SHARES_POR_ORDEM"]
            price_decimal = Decimal(str(preco_venda))
            
            order_args = OrderArgs(
                price=price_decimal,
                size=str(quantidade),
                side=SELL,
                token_id=self.config["TOKEN_ID"],
            )
            
            resultado = await self.client.create_order(order_args)
            
            if resultado:
                # Extrair ID
                ordem_id = ""
                if hasattr(resultado, 'id'):
                    ordem_id = resultado.id
                elif isinstance(resultado, dict):
                    ordem_id = resultado.get('id', '')
                
                if ordem_id:
                    self.ordens_venda_ativas[preco_compra] = ordem_id
                    lucro = self.config["LUCRO_POR_OPERACAO"]
                    print(f"💰 VENDA criada: {quantidade} @ ${preco_venda:.2f}")
                    print(f"   📈 Lucro potencial: ${lucro * quantidade:.2f}")
                    return True
            
            return False
            
        except Exception as e:
            print(f"⚠️  Erro na venda @ ${preco_venda:.2f}: {str(e)[:50]}...")
            return False
    
    async def _atualizar_controle_ordens(self):
        """Atualiza controle interno com ordens atuais"""
        ordens = await self._obter_ordens_abertas()
        
        # Limpar listas
        self.ordens_compra_ativas.clear()
        self.ordens_venda_ativas.clear()
        
        # Reconstruir com ordens atuais
        for ordem in ordens:
            preco = ordem['price']
            ordem_id = ordem['id']
            
            if ordem['side'] == 'buy':
                self.ordens_compra_ativas[preco] = ordem_id
            elif ordem['side'] == 'sell':
                # Encontrar qual compra corresponde a esta venda
                for compra in self.posicoes_compradas:
                    if self._calcular_preco_venda(compra) == preco:
                        self.ordens_venda_ativas[compra] = ordem_id
                        break
    
    async def executar_ciclo(self):
        """Executa um ciclo completo do robô"""
        self.ciclo_numero += 1
        
        print(f"\n{'='*60}")
        print(f"🔄 CICLO {self.ciclo_numero} - {time.strftime('%H:%M:%S')}")
        print(f"{'='*60}")
        
        # 1. Atualizar controle de ordens
        await self._atualizar_controle_ordens()
        
        print(f"📊 STATUS ATUAL:")
        print(f"   • Ordens de COMPRA ativas: {len(self.ordens_compra_ativas)}")
        print(f"   • Ordens de VENDA ativas: {len(self.ordens_venda_ativas)}")
        print(f"   • Posições compradas: {len(self.posicoes_compradas)}")
        
        # 2. Verificar ordens executadas e criar vendas
        await self._verificar_ordens_executadas()
        
        # 3. Criar novas ordens de compra (grid)
        print(f"\n🔵 CRIANDO NOVAS ORDENS DE COMPRA...")
        ordens_novas = 0
        
        for preco in self.grid_compras:
            if ordens_novas >= 2:  # Cria no máximo 2 ordens por ciclo
                break
            
            if await self._criar_ordem_compra(preco):
                ordens_novas += 1
                await asyncio.sleep(1)  # Pausa para evitar rate limit
        
        # 4. Resumo
        print(f"\n📋 RESUMO DO CICLO:")
        print(f"   • Ordens de compra novas: {ordens_novas}")
        print(f"   • Total ordens ativas: {len(self.ordens_compra_ativas) + len(self.ordens_venda_ativas)}")
        
        # Mostrar ordens ativas
        if self.ordens_compra_ativas:
            print(f"\n🛒 COMPRAS PENDENTES:")
            for preco, ordem_id in list(self.ordens_compra_ativas.items())[:3]:
                print(f"   • ${preco:.2f}")
        
        if self.ordens_venda_ativas:
            print(f"\n💰 VENDAS PENDENTES:")
            for preco_compra, ordem_id in list(self.ordens_venda_ativas.items())[:3]:
                preco_venda = self._calcular_preco_venda(preco_compra)
                lucro = self.config["LUCRO_POR_OPERACAO"]
                print(f"   • Compra: ${preco_compra:.2f} → Venda: ${preco_venda:.2f} (+${lucro:.2f})")
        
        print(f"\n⏳ Próximo ciclo em {self.config['INTERVALO_CICLO']} segundos...")
        print(f"{'='*60}")
    
    async def iniciar(self):
        """Inicia o robô"""
        print("\n" + "="*60)
        print("🚀 INICIANDO ROBÔ GRID TRADING COMPLETO")
        print("="*60)
        print("⚠️  IMPORTANTE: Este robô faz:")
        print("   1. COMPRAS automáticas em grid")
        print("   2. VENDAS automáticas com lucro fixo")
        print("   3. Trabalha 100% sozinho no Railway")
        print("="*60)
        
        # AVISO DE TESTNET
        if self.testnet:
            print("✅ MODO TESTNET ATIVADO - Sem risco real")
        else:
            print("⚠️  ⚠️  ⚠️  MODO MAINNET - DINHEIRO REAL! ⚠️  ⚠️  ⚠️")
        
        print(f"📊 Grid: ${self.config['COMPRA_INICIO']} até ${self.config['COMPRA_FIM']}")
        print(f"💰 Lucro: ${self.config['LUCRO_POR_OPERACAO']} por share")
        print(f"⏱️  Intervalo: {self.config['INTERVALO_CICLO']}s")
        print("="*60)
        
        # Começar do ZERO: cancelar tudo
        await self._cancelar_todas_ordens()
        
        # Loop principal
        try:
            while True:
                await self.executar_ciclo()
                await asyncio.sleep(self.config["INTERVALO_CICLO"])
                
        except KeyboardInterrupt:
            print("\n\n🛑 ROBÔ PARADO PELO USUÁRIO")
        except Exception as e:
            print(f"\n❌ ERRO CRÍTICO: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n📊 RESUMO FINAL:")
        print(f"   • Ciclos executados: {self.ciclo_numero}")
        print(f"   • Posições compradas: {len(self.posicoes_compradas)}")
        print(f"   • Vendas criadas: {len(self.ordens_venda_ativas)}")
        print("="*60)

async def main():
    """Função principal"""
    print("🚀 INICIANDO ROBÔ GRID TRADING...")
    
    # Verificar private key
    if not CONFIG["PRIVATE_KEY"]:
        print("❌ ERRO: PRIVATE_KEY não configurada!")
        print("\n📋 COMO CONFIGURAR:")
        print("1. Railway → Variables")
        print("2. Add: PRIVATE_KEY=sua_chave_aqui")
        print("3. Save & Deploy")
        return
    
    # Verificar configurações
    print(f"\n🔧 CONFIGURAÇÃO VERIFICADA:")
    print(f"   • TESTNET: {'✅' if CONFIG['TESTNET'] else '❌'}")
    print(f"   • Shares por ordem: {CONFIG['SHARES_POR_ORDEM']}")
    print(f"   • Lucro alvo: ${CONFIG['LUCRO_POR_OPERACAO']}")
    
    if CONFIG["SHARES_POR_ORDEM"] > 1 and CONFIG["TESTNET"]:
        print(f"\n⚠️  AVISO: Comece com SHARES_POR_ORDEM = 1 para testes!")
    
    # Pequena pausa
    await asyncio.sleep(3)
    
    try:
        robo = RoboGridCompleto(CONFIG)
        await robo.iniciar()
    except Exception as e:
        print(f"❌ ERRO NA INICIALIZAÇÃO: {e}")

if __name__ == "__main__":
    asyncio.run(main())
