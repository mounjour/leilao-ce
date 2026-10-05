"""Paginas legais publicas (Termos de Uso, Privacidade, Cancelamento e Reembolso).

Acessiveis sem login via ?pagina=termos|privacidade|reembolso. _CONTROLADOR
identifica o responsavel (CNPJ); mude ATUALIZADO_EM ao alterar os textos.
"""
import streamlit as st

SITE = "achadinleiloes.tech"
CONTATO = "alissonerllen3@gmail.com"
ATUALIZADO_EM = "05/10/2026"
_CONTROLADOR = "Alisson Erllen dos Santos Silva, inscrito no CNPJ 57.445.137/0001-77"

PAGINAS = {
    "termos": "Termos de Uso",
    "privacidade": "Política de Privacidade",
    "reembolso": "Cancelamento e Reembolso",
}

_TERMOS = f"""
Estes Termos regem o uso do **Achadin Leilões** (`{SITE}`), serviço operado por
{_CONTROLADOR} ("nós"). Ao criar uma conta ou assinar, você declara que leu e
aceita estes Termos.

### 1. O que o serviço é
O Achadin Leilões reúne, em um só lugar, informações públicas de leilões no
Ceará, publicadas por leiloeiros e órgãos terceiros, com filtros, comparação
com a tabela FIPE, análise de oportunidade gerada por inteligência artificial e
alertas por WhatsApp.

**Não somos leiloeiros, não vendemos os bens e não participamos dos leilões.**
Qualquer lance, compra ou pagamento é feito diretamente no site do leiloeiro
responsável, sob as regras dele.

### 2. Informações podem conter erros
Os dados são coletados automaticamente (atualização 2 vezes ao dia) e podem
estar incompletos, desatualizados ou incorretos. Valores, datas, fotos,
situação do bem e dados da FIPE devem ser **sempre conferidos no edital e no
site do leiloeiro** antes de qualquer decisão.

A análise de IA e a indicação de "oportunidade" são apoio automatizado e
**não constituem recomendação de investimento, avaliação oficial, laudo ou
consultoria jurídica**. Leilões envolvem riscos (dívidas, ocupação, vícios
ocultos, restrições documentais). A decisão e o risco são seus. Não nos
responsabilizamos por prejuízos decorrentes de lances ou compras feitos com
base nas informações do serviço, nos limites da lei.

### 3. Conta
- Você deve ter 18 anos ou mais e fornecer dados verdadeiros (nome, e-mail e
  WhatsApp).
- Você é responsável pela guarda da sua senha e pelo que ocorre na sua conta.
- A conta é pessoal e não pode ser compartilhada ou revendida.

### 4. Assinatura e pagamento
- O acesso completo é pago, por assinatura mensal, com o valor exibido na tela
  de assinatura antes da contratação.
- O pagamento é processado pelo **Stripe**; não armazenamos dados do seu cartão.
- A cobrança é recorrente e renovada automaticamente a cada mês até o
  cancelamento.
- Podemos reajustar o preço, avisando com antecedência razoável; o novo valor
  só vale a partir do ciclo seguinte ao aviso.
- Cancelamento e reembolso: veja a página
  [Cancelamento e Reembolso](?pagina=reembolso).

### 5. Alertas por WhatsApp
Ao informar seu número, você autoriza o envio de alertas do serviço. O envio
depende de serviços de terceiros e **não é garantido** (falhas, atrasos ou
indisponibilidade podem ocorrer). Você pode pedir a remoção do número a
qualquer momento.

### 6. Uso aceitável
É proibido: usar robôs ou coleta automatizada para copiar o conteúdo do
serviço, revender ou redistribuir os dados, tentar burlar o acesso pago,
sobrecarregar ou atacar a plataforma, ou usá-la para fins ilícitos.
Podemos suspender ou encerrar contas que violem estes Termos.

### 7. Propriedade intelectual
O código, a marca e a organização do serviço são nossos. Os dados originais
dos lotes (textos, fotos, marcas) pertencem aos respectivos leiloeiros e
terceiros e são exibidos com link para a origem.

### 8. Disponibilidade e mudanças
O serviço é fornecido "como está", sem garantia de funcionamento
ininterrupto. Podemos alterar, suspender ou encerrar funcionalidades ou fontes
de dados (por exemplo, quando um leiloeiro bloqueia a coleta). Mudanças
relevantes nestes Termos serão comunicadas no site ou por e-mail; continuar
usando após o aviso significa aceitar a nova versão.

### 9. Limitação de responsabilidade
Na máxima extensão permitida pela lei (inclusive o Código de Defesa do
Consumidor, que continua valendo), nossa responsabilidade fica limitada ao
valor pago por você nos 12 meses anteriores ao fato, e não respondemos por
lucros cessantes ou danos indiretos.

### 10. Lei e foro
Estes Termos seguem a lei brasileira. Fica eleito o foro do domicílio do
consumidor, conforme o CDC.

### 11. Contato
Dúvidas, solicitações e reclamações: **{CONTATO}**.
"""

_PRIVACIDADE = f"""
Esta Política explica como o **Achadin Leilões** (`{SITE}`) trata dados
pessoais, conforme a Lei Geral de Proteção de Dados (LGPD, Lei 13.709/2018).

**Controlador:** {_CONTROLADOR}.
**Contato e encarregado (DPO):** {CONTATO}.

### 1. Dados que coletamos
| Dado | Para quê | Base legal (LGPD) |
|---|---|---|
| Nome, e-mail, senha (armazenada criptografada) | Criar e acessar sua conta | Execução de contrato |
| Número de WhatsApp | Enviar alertas de leilões que você pediu | Execução de contrato / consentimento |
| Status e identificadores da assinatura (ID de cliente/assinatura Stripe, status, datas) | Liberar o acesso pago, cobrar e cancelar | Execução de contrato |
| Favoritos e filtros que você salva | Entregar as funções do serviço | Execução de contrato |
| Registros técnicos (falhas de envio de WhatsApp, logs do servidor) | Segurança, diagnóstico e prevenção a fraude | Legítimo interesse |

**Não armazenamos número, validade ou CVV do seu cartão.** Isso fica com o Stripe.
Não coletamos dados sensíveis (art. 5º, II da LGPD).

### 2. Com quem compartilhamos (operadores)
Só o necessário para o serviço funcionar:
- **Supabase**: banco de dados e autenticação (login, perfil, favoritos).
- **Stripe**: pagamentos e portal de cobrança.
- **Hostinger**: hospedagem do servidor.
- **Provedor de envio de WhatsApp** (instância própria da API Evolution): entrega dos alertas.
- **Anthropic**: apenas para a análise de IA dos *lotes*; **não enviamos seus dados pessoais**.

Alguns desses provedores ficam fora do Brasil, o que caracteriza transferência
internacional de dados, feita com base em contrato e nas salvaguardas dos
próprios provedores (art. 33 da LGPD). **Não vendemos seus dados** e não os
usamos para publicidade de terceiros.

### 3. Por quanto tempo guardamos
Enquanto sua conta existir. Ao excluí-la, apagamos ou anonimizamos os dados
pessoais em até 30 dias, exceto o que a lei exigir guardar (por exemplo,
registros fiscais e de pagamento, geralmente por 5 anos) ou o necessário para
defesa em processos.

### 4. Seus direitos (art. 18)
Você pode pedir: confirmação de tratamento, acesso, correção, anonimização ou
eliminação, portabilidade, informação sobre compartilhamento, e revogação do
consentimento (por exemplo, parar de receber WhatsApp). Escreva para
**{CONTATO}**; respondemos em até 15 dias. Você também pode reclamar à
Autoridade Nacional de Proteção de Dados (ANPD).

### 5. Cookies
Usamos apenas armazenamento essencial para manter você logado e o app
funcionando. Não usamos cookies de publicidade.

### 6. Segurança
Conexão HTTPS, senhas com hash, acesso ao banco restrito por usuário (RLS) e
chaves de serviço guardadas fora do código. Nenhum sistema é 100% seguro; em
caso de incidente relevante, comunicaremos você e a ANPD conforme a lei.

### 7. Alterações
Podemos atualizar esta Política; a data no topo indica a versão vigente.
"""

_REEMBOLSO = f"""
Valem para a assinatura do **Achadin Leilões** (`{SITE}`).

### 1. Cancelar quando quiser
Você cancela sozinho, a qualquer momento, pelo **portal de cobrança** (menu do
usuário, ou botão "Abrir portal de cobrança" na tela de assinatura). Não há
multa nem fidelidade.

Ao cancelar, **nenhuma nova cobrança é feita** e você continua com acesso até o
fim do período já pago.

### 2. Direito de arrependimento: 7 dias
Como a contratação é online, vale o art. 49 do Código de Defesa do
Consumidor: você pode desistir em até **7 dias corridos contados da primeira
cobrança** e receber **100% do valor de volta**, sem precisar justificar.

Para pedir, escreva para **{CONTATO}** com o e-mail da conta. O estorno é
feito pelo Stripe no mesmo meio de pagamento; o prazo para aparecer na fatura
depende do banco/operadora (geralmente até 2 faturas). Respondemos em até 5
dias úteis.

### 3. Depois dos 7 dias
Não há reembolso proporcional do mês em curso: o cancelamento vale para a
próxima renovação e o acesso segue até o fim do ciclo já pago.

### 4. Exceções em que devolvemos
- **Cobrança em duplicidade ou indevida** (inclusive após cancelamento).
- **Falha nossa que impeça o uso do serviço** por período relevante.

### 5. Renovações
O direito dos 7 dias vale para a primeira contratação. Se você esqueceu de
cancelar e foi cobrado numa renovação, escreva em até 7 dias da cobrança e
avaliaremos o estorno caso você não tenha usado o serviço no período.

### 6. Contato
**{CONTATO}**
"""

_CORPO = {"termos": _TERMOS, "privacidade": _PRIVACIDADE, "reembolso": _REEMBOLSO}


def links_markdown() -> str:
    """Rodape com links para as tres paginas (abrem em nova aba)."""
    return " · ".join(f"[{titulo}](?pagina={chave})" for chave, titulo in PAGINAS.items())


def render_legal(pagina: str) -> None:
    """Renderiza a pagina legal pedida e deixa o app seguir sem login."""
    st.title(PAGINAS[pagina])
    st.caption(f"Última atualização: {ATUALIZADO_EM}")
    st.markdown(_CORPO[pagina])
    st.divider()
    st.markdown(links_markdown())
    st.markdown("[← Voltar ao site](/)")


def pagina_legal_solicitada() -> str | None:
    """Retorna a chave da pagina legal em ?pagina=, ou None."""
    valor = str(st.query_params.get("pagina", ""))
    return valor if valor in PAGINAS else None
