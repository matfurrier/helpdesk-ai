"""Seed KB v3 — 9 artigos adicionais de helpdesk.

Run:
    docker cp scripts/seed_kb_v3.py helpdesk-backend:/app/scripts/
    docker exec helpdesk-backend python /app/scripts/seed_kb_v3.py

Idempotent: ON CONFLICT (slug) DO NOTHING.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field

SEED_USER_ID = "00000000-0000-0000-0000-000000000001"


@dataclass
class Article:
    slug: str
    title: str
    tags: list[str]
    body: str
    trust_level: str = "internal_published"


ARTICLES: list[Article] = [
    # ------------------------------------------------------------------
    Article(
        slug="certificado-digital",
        title="Certificado Digital — Instalação, Desinstalação e Renovação",
        tags=["certificado", "a1", "a3", "fsist", "token", "assinatura", "validade"],
        body="""\
## Certificado Digital — Instalação, Desinstalação e Renovação

Certificados digitais são usados para assinatura eletrônica de documentos, acesso a sistemas governamentais (e-CAC, SEFAZ, FSIST) e autenticação segura. Existem dois tipos: **A1** (arquivo no computador) e **A3** (token físico USB ou cartão).

---

### Sintomas comuns

- Sistema não reconhece o certificado ao tentar assinar ou autenticar
- Mensagem "Certificado expirado" ou "Certificado inválido"
- Token A3 não é detectado pelo computador (sem driver ou driver corrompido)
- Certificado A1 some após formatação ou troca de computador
- Erro ao acessar FSIST, e-CAC ou portal da SEFAZ
- Solicitação de senha do certificado que não é lembrada

---

### O que o usuário NÃO deve tentar sozinho

- **Não instale drivers de token por conta própria** — versões erradas corrompem o ambiente e impedem o funcionamento de outros certificados
- **Não tente "reparar" o certificado** deletando arquivos do Windows — pode invalidar outros certificados instalados
- **Não tente renovar o certificado diretamente** — a renovação envolve processo junto à autoridade certificadora (AC) e tem custo; o TI coordena esse processo
- **Não formate o computador** achando que vai resolver — o certificado A1 pode ser perdido permanentemente
- **Não revele a senha do certificado** — nem para o TI; o TI nunca pede essa senha

---

### O que tentar antes de acionar o TI

**Certificado A3 (token USB) não reconhecido:**
1. Desconecte e reconecte o token em outra porta USB (evite hub/extensão)
2. Reinicie o computador com o token conectado
3. Verifique no Gerenciador de Dispositivos se aparece com sinal de exclamação

**Certificado A1 não aparece no sistema:**
1. Confirme que o arquivo `.pfx` foi instalado: Win + R → `certmgr.msc` → "Pessoal" → "Certificados"
2. Verifique se o certificado está dentro da validade (data "Válido até")

---

### Quando acionar o TI (obrigatório)

- Certificado expirado — processo de renovação
- Token A3 não reconhecido após os passos básicos
- Certificado A1 precisa ser migrado para novo computador
- Erro de acesso em sistema governamental (FSIST, e-CAC, SEFAZ)
- Primeira instalação de certificado

**Informações para o chamado:**
- Qual sistema usa o certificado (FSIST, SEFAZ, e-CAC, outro?)
- Tipo: A1 (arquivo) ou A3 (token físico)?
- A data de validade do certificado (se souber)
- Mensagem de erro exata (print de tela)
- O certificado funciona em outro computador?
""",
    ),
    # ------------------------------------------------------------------
    Article(
        slug="email-caixa-cheia-lista",
        title="E-mail — Caixa Cheia e Inclusão em Listas Corporativas",
        tags=["email", "outlook", "caixa-cheia", "lista-distribuicao", "comercial", "quota", "grupo"],
        body="""\
## E-mail — Caixa Cheia e Inclusão em Listas Corporativas

---

### Parte 1 — Caixa de E-mail Cheia

**Sintomas:** E-mails voltando com "Caixa de correio cheia" ou "Quota excedida"; não consegue enviar ou receber; Outlook avisa sobre espaço insuficiente.

**Como liberar espaço (faça você mesmo):**

1. **Esvaziar a Lixeira do Outlook:**
   Painel Esquerdo → clique com botão direito em "Itens Excluídos" → "Esvaziar pasta" — itens excluídos continuam ocupando espaço até serem removidos da lixeira

2. **Esvaziar a pasta Lixo Eletrônico (Spam):**
   Clique com botão direito em "Lixo Eletrônico" → "Esvaziar pasta Lixo Eletrônico"

3. **Apagar e-mails com anexos grandes:**
   No Outlook: Exibição → "Organizar por" → Tamanho → identifique e-mails grandes → selecione e delete
   Atalho: na caixa de pesquisa do Outlook, digite `tamanho:enorme` ou `hasattachments:yes` para filtrar

4. **Arquivar e-mails antigos:**
   Arquivo → Ferramentas → Limpar Caixa de Correio → "Arquivar itens mais antigos que" → defina uma data (ex.: 1 ano atrás)
   Ou: clique com botão direito em uma pasta → Propriedades → "Arquivamento Automático"

5. **Verificar a pasta Itens Enviados:**
   E-mails enviados com anexos grandes ficam na pasta "Itens Enviados" — apague os desnecessários

**Política de retenção e limite da caixa:**
- Limite padrão de caixa: definido pela política de TI (consulte o TI para saber o seu limite atual)
- E-mails são retidos por no mínimo 90 dias — após esse período podem ser movidos para arquivo conforme política corporativa
- Anexos não devem ser o repositório principal de documentos — use o SharePoint ou pastas de rede para armazenar arquivos

**Quando acionar o TI:** Após liberar espaço, o problema persistir; necessidade de aumento permanente da quota; e-mails críticos perdidos.

---

### Parte 2 — Inclusão em Lista ou Grupo de E-mail Corporativo

**O que é:** Listas de distribuição são grupos de e-mail que entregam mensagens para vários destinatários de uma vez (ex.: comercial@empresa.com, producao@empresa.com).

**Esta é uma solicitação para o TI — não é possível fazer sozinho.**

**Como solicitar:**
Abra um chamado no helpdesk informando:
- Nome completo do colaborador a ser incluído
- E-mail corporativo do colaborador
- Nome ou endereço da lista de distribuição (ex.: "lista-comercial", "todos-produção")
- Motivo da inclusão (mudança de setor, novo colaborador, etc.)
- Se é para adicionar ou remover da lista

**Prazo:** até 1 dia útil após a solicitação.

**Importante:** Listas de distribuição por departamento (ex.: Comercial, Produção, Logística) exigem aprovação do gestor responsável pela lista.
""",
    ),
    # ------------------------------------------------------------------
    Article(
        slug="acesso-pastas-rede",
        title="Pastas de Rede — Solicitação de Acesso e Configuração de Caminho",
        tags=["pasta", "rede", "acesso", "permissao", "mapeamento", "dsdocumentos", "sinal600", "caminho", "drive"],
        body="""\
## Pastas de Rede — Solicitação de Acesso e Configuração de Caminho

---

### Diferença entre Pasta de Rede e SharePoint

| | Pasta de Rede | SharePoint |
|--|---|---|
| Como acessa | Drive mapeado no Explorer (ex.: Z:, W:) | Navegador web ou OneDrive |
| Endereço | `\\\\servidor\\pasta` | URL .sharepoint.com |
| Acesso externo | Requer VPN | Direto pelo navegador (com conta corporativa) |
| Backup | Feito pelo servidor | Microsoft Cloud |
| Ideal para | Arquivos grandes, sistemas legados | Colaboração, documentos de equipe |

---

### Parte 1 — Solicitar Acesso a uma Pasta de Rede

**Esta é uma solicitação para o TI — acesso não pode ser concedido pelo próprio usuário.**

**O que informar no chamado:**
- **Nome completo** do colaborador que precisa de acesso
- **Caminho completo** da pasta (ex.: `\\\\dsdocumentos\\comercial\\contratos` ou `\\\\sinal600\\producao`)
- **Nível de acesso necessário:** somente leitura ou leitura e escrita (edição)
- **Justificativa:** por que precisa do acesso (mudança de função, novo projeto, etc.)
- **Gestor que aprova:** nome e e-mail do responsável pela pasta (o TI solicita confirmação ao gestor)

**Prazo:** até 1 dia útil após confirmação do gestor.

**Atenção:** O TI não concede acesso sem aprovação do gestor responsável pela pasta — isso é parte da política de segurança da informação.

---

### Parte 2 — Configurar Mapeamento de Pasta (Drive Mapeado)

Se a pasta existe e você tem acesso, mas o drive não aparece no Explorer:

**Para mapear manualmente:**
1. Abra o Explorer (Win + E)
2. Clique em "Este Computador" no painel esquerdo
3. Menu superior → "Computador" → "Mapear Unidade de Rede"
4. Escolha a letra do drive (ex.: Z:)
5. No campo "Pasta", digite o caminho completo (ex.: `\\\\dsdocumentos\\comercial`)
6. Marque "Reconectar ao fazer logon" → Concluir

**Se o mapeamento automático sumiu (era configurado pelo TI):**
- Pode ter ocorrido após troca de senha, reconfiguração de domínio ou formatação
- Acione o TI informando: nome da pasta, letra do drive que costumava ter, e nome do computador

**Informações para o chamado de mapeamento:**
- Nome da pasta (ex.: "DSDocumentos", "Sinal600")
- Letra ou localização onde deve aparecer no Explorer
- Nome do computador (Win + Pausa → "Nome do Computador")
- Seu usuário de rede

---

### Parte 3 — Pasta sumiu ou arquivo deletado

- Pastas de rede têm backup diário — arquivos deletados podem ser recuperados
- O TI pode restaurar versões anteriores (até 30 dias, conforme política de backup)
- Informe: caminho da pasta/arquivo, data aproximada em que existia, se foi você ou outro usuário que deletou
""",
    ),
    # ------------------------------------------------------------------
    Article(
        slug="telefonia-ramal",
        title="Telefonia — Ramal sem Funcionamento",
        tags=["telefone", "ramal", "telefonia", "voip", "sem-linha", "nao-toca"],
        body="""\
## Telefonia — Ramal sem Funcionamento

---

### Sintomas comuns

- Ramal não toca ao receber chamadas
- Não há tom de discagem ao tentar ligar
- Chamadas caem durante a conversa
- Qualidade ruim de áudio (eco, chiado, voz cortada)
- Telefone não liga / sem energia
- Ramal discando mas não completa a chamada

---

### O que tentar antes de acionar o TI

**Passo 1 — Verifique os cabos:**
- Confira se o cabo de rede (RJ-45) está firmemente conectado tanto no telefone quanto na tomada da parede
- Para telefones VoIP: o cabo de rede alimenta o aparelho — se solto, o telefone perde energia
- Tente desconectar e reconectar o cabo

**Passo 2 — Reinicie o aparelho:**
- Desconecte o cabo de rede do telefone, aguarde 10 segundos, reconecte
- Para aparelhos com fonte de alimentação própria: desligue da tomada, aguarde 10 segundos, religue

**Passo 3 — Teste em outro ramal:**
- Tente ligar de outro telefone para o seu ramal — se não toca, pode ser problema no ramal
- Tente usar o telefone com problema em outro ponto de rede (outra sala ou mesa) — se funcionar, o problema é no cabeamento do ponto

**Passo 4 — Verifique se é problema localizado:**
- Pergunte aos colegas do mesmo setor se estão com o mesmo problema
- Se vários ramais do mesmo setor estão falhando → possível queda do switch ou do servidor de telefonia → acione TI com urgência

---

### Quando acionar o TI

- Nenhum dos passos acima resolve
- Problema afeta múltiplos ramais do mesmo setor
- Necessidade de configurar novo ramal ou transferir ramal para outra sala
- Configurar desvio de chamadas ou caixa postal
- Telefone fisicamente danificado

**Informações para o chamado:**
- Número do ramal com problema (impresso no aparelho ou consultável com TI)
- Setor e localização (sala, andar, filial)
- Tipo do problema: não toca, sem tom, cai chamada, sem áudio
- Quando o problema começou
- Outros ramais na mesma área estão com problema?
""",
    ),
    # ------------------------------------------------------------------
    Article(
        slug="instalacao-software-programa",
        title="Instalação de Software e Programas",
        tags=["instalacao", "programa", "software", "conversor", "driver", "permissao-admin", "bloqueio", "licenca"],
        body="""\
## Instalação de Software e Programas

---

### Por que não consigo instalar programas?

A política de TI bloqueia a instalação de software por usuários padrão — **isso é intencional e uma medida de segurança**. Programas instalados sem avaliação podem:
- Conter vírus ou ransomware disfarçados
- Violar licenças de uso (risco jurídico)
- Conflitar com sistemas existentes
- Abrir vulnerabilidades de segurança

Se aparecer a mensagem "Você não tem permissão para instalar este programa" ou a tela pede "senha de administrador" — **não tente contornar**. Abra um chamado no TI.

---

### Como solicitar instalação de um programa

**Abra um chamado no helpdesk informando:**

1. **Nome do programa e versão** (ex.: "Adobe Acrobat Reader DC 2024", "7-Zip 23.01")
2. **Fabricante/site oficial** (ex.: adobe.com, 7-zip.org) — ajuda o TI a baixar da fonte correta
3. **Justificativa de uso** — para que será usado? Qual atividade de trabalho?
4. **Quais máquinas** precisam receber o software (hostname ou patrimônio do computador)
5. **Urgência real** — se é para projeto/auditoria/apresentação com data, informe

**Prazo estimado:**
- Programas gratuitos e já avaliados pelo TI: até 1 dia útil
- Programas novos que precisam de avaliação de segurança: 3 a 5 dias úteis
- Programas pagos (necessidade de licença): depende de aprovação e aquisição

---

### Programas que precisam de avaliação de segurança antes de instalar

O TI avalia antes de aprovar:
- Qualquer software de acesso remoto (AnyDesk, TeamViewer, etc.) — liberado apenas para uso corporativo controlado
- Programas que modificam o sistema operacional ou o registro do Windows
- Conversores de PDF, compactadores e utilitários de terceiros desconhecidos
- Plugins e extensões de navegador que solicitam permissões amplas
- Qualquer software recebido por e-mail, link ou pendrive externo

---

### Programas comuns já pré-aprovados (o TI instala sem avaliação adicional)

- Adobe Acrobat Reader (leitura de PDF)
- 7-Zip ou WinRAR (compactação)
- VLC Media Player
- Google Chrome / Microsoft Edge
- LibreOffice (suíte de escritório gratuita)
- Zoom / Microsoft Teams (conforme licença corporativa)

**Para esses, o prazo é de até 1 dia útil após o chamado.**

---

### Drivers de hardware (impressora, scanner, etc.)

Drivers também precisam ser instalados pelo TI. Ao solicitar, informe:
- Modelo exato do equipamento (impresso na etiqueta)
- Sistema operacional (Windows 10 ou 11)
- Se o equipamento era de outra máquina ou é novo
""",
    ),
    # ------------------------------------------------------------------
    Article(
        slug="computador-perdeu-dominio",
        title="Computador Saiu do Domínio / Pede Senha de Administrador",
        tags=["dominio", "active-directory", "senha-adm", "windows", "nao-consigo-mexer", "login", "perfil"],
        body="""\
## Computador Saiu do Domínio / Pede Senha de Administrador

---

### Sintomas — Como identificar o problema

- Ao ligar o computador, aparece uma mensagem como: **"O relacionamento de confiança entre esta estação de trabalho e o domínio principal falhou"**
- Windows pede senha de administrador para qualquer ação (instalar, alterar configuração)
- Seu login corporativo (usuário de rede) não é reconhecido: "Usuário ou senha incorretos" mesmo com a senha certa
- Computador aparece com o nome de usuário local em vez do nome de domínio
- Ícones e configurações do perfil somem ou aparecem como "perfil temporário"

---

### Por que acontece?

O computador faz parte de um Domínio Active Directory (AD) — que é o sistema central que gerencia todos os usuários e permissões. Quando o computador "sai do domínio", ele perde a comunicação com esse servidor central, o que faz com que logins corporativos não sejam reconhecidos. As causas mais comuns são:

- Computador ficou desligado por muito tempo sem se conectar à rede corporativa
- Troca de placa de rede ou mudança de IP sem atualização no AD
- Problema durante atualização do Windows
- Formatação ou reinstalação do sistema sem reentrada no domínio

---

### O que o usuário NÃO deve tentar resolver sozinho

- **Não tente entrar com senha de administrador local** — mesmo que apareça essa opção, pode agravar o problema ou violar a política de segurança
- **Não reinstale o Windows** — não resolve a desconexão do domínio e apaga dados
- **Não tente reentrar manualmente no domínio** — requer credenciais de administrador do AD que somente o TI possui
- **Não use o computador** para trabalho enquanto estiver fora do domínio — configurações de segurança não estão ativas

---

### O que fazer: acione o TI imediatamente

Este problema **não tem solução pelo usuário**. O TI precisa entrar com credenciais de administrador do domínio para reconectar o computador.

**Informações para o chamado (quanto mais informações, mais rápido o atendimento):**
- **Nome do computador:** clique com botão direito em "Este Computador" → Propriedades → "Nome do computador"
- **Número de patrimônio:** etiqueta colada no computador (geralmente começa com números)
- **Setor e localização:** sala, andar, filial
- **Mensagem de erro exata** (foto ou print da tela)
- **Quando começou** (após atualização do Windows? Após longa folga? Após formatação?)
- **Você consegue logar com algum usuário?** (local, anterior, etc.)

**Prioridade:** este é um chamado de alta prioridade — o colaborador fica sem acesso ao ambiente de trabalho.
""",
    ),
    # ------------------------------------------------------------------
    Article(
        slug="hardware-performance",
        title="Computador Lento, Travando ou com Problema de Hardware",
        tags=["lento", "travando", "memoria-ram", "cpu", "hardware", "driver", "audio", "video", "formatacao"],
        body="""\
## Computador Lento, Travando ou com Problema de Hardware

---

### Diagnóstico rápido — o que verificar primeiro

**Verifique o uso de memória RAM e CPU:**
1. Pressione **Ctrl + Alt + Del** → "Gerenciador de Tarefas" → aba "Desempenho"
2. Observe os valores de **CPU** e **Memória**:
   - CPU > 90% por mais de 1 minuto → processo consumindo muito
   - Memória > 90% → insuficiente para o uso atual
3. Na aba "Processos", clique em "CPU" ou "Memória" para ordenar — identifique o processo que mais consome
4. Se um processo desconhecido está consumindo tudo → anote o nome e acione o TI (pode ser vírus)

**Verificações rápidas:**
- Reinicie o computador — muitos travamentos são resolvidos com restart
- Verifique se há atualizações do Windows instalando em segundo plano (ícone de atualização na bandeja)
- Feche programas que não estão sendo usados (especialmente navegadores com muitas abas)
- Verifique espaço em disco: Este Computador → disco C: → se estiver com menos de 10% livre, o sistema fica lento

---

### Driver de áudio/vídeo com problema

**Sintomas:** sem som, som distorcido, tela piscando, resolução incorreta, driver de vídeo travando.

**NÃO instale drivers manualmente pelo site do fabricante** — versões incompatíveis podem piorar o problema e conflitar com outros drivers.

O correto é:
1. Descreva o sintoma no chamado ao TI
2. O TI identifica o driver correto para o modelo do computador e instala com as configurações adequadas

**Exceção:** o Windows Update pode instalar drivers automaticamente — isso é seguro e pode resolver o problema.

---

### Quando formatar é necessário vs. quando não é

| Situação | Formatar? |
|----------|-----------|
| Computador lento mas funcional | Não — TI faz limpeza e otimização primeiro |
| Vírus confirmado que não remove por antivírus | Sim — TI formata e reinstala |
| Sistema corrompido após falha grave | Sim — TI avalia |
| Problemas de driver recorrentes | Não necessariamente — TI tenta restauração de sistema primeiro |
| Computador saiu do domínio | Não — formatação não resolve, TI reconecta ao domínio |
| HD/SSD com setores defeituosos | Sim, mas com troca de hardware antes |

**Importante:** A formatação apaga todos os dados do computador. O TI faz backup antes de formatar, mas **o usuário deve verificar se todos os documentos importantes estão salvos no servidor ou SharePoint**.

---

### Informações para passar ao TI no chamado

- **Modelo do computador** (etiqueta do fabricante ou Painel de Controle → Sistema)
- **Número de patrimônio** (etiqueta colada no equipamento)
- **Sintoma detalhado:** trava ao abrir qual programa? Em que momento do dia? Temperatura anormal?
- **Quando começou:** após atualização? Após instalar algo? Sempre foi assim?
- **Urgência:** o computador está inutilizável ou apenas mais lento?
- Print do Gerenciador de Tarefas mostrando o uso de CPU/memória
""",
    ),
    # ------------------------------------------------------------------
    Article(
        slug="internet-fraca-sem-conexao",
        title="Internet Fraca ou Sem Conexão",
        tags=["internet", "wifi", "cabo", "conexao", "lento", "rede", "producao", "barracao", "sem-internet"],
        body="""\
## Internet Fraca ou Sem Conexão

---

### Primeiro passo: isolamento do problema

Antes de acionar o TI, determine se o problema é:

**A) Só naquele computador:**
- Teste outro computador na mesma mesa/sala — se funcionar, é problema local
- Tente conectar pelo cabo (se estava no Wi-Fi) ou pelo Wi-Fi (se estava no cabo)

**B) Vários computadores do mesmo setor:**
- Pergunte aos colegas ao redor — se vários estão sem acesso → problema de rede do setor (switch, ponto de acesso, roteador)
- Acione o TI com urgência informando quantas máquinas estão afetadas

**C) Acesso à internet específico:**
- Alguns sites bloqueados? Pode ser política do proxy corporativo — tente outro site
- Só sistemas internos sem acesso? Pode ser problema de VPN ou DNS

---

### O que tentar antes de acionar o TI

**Reiniciar o computador:**
- Resolve a maioria dos problemas de adaptador de rede travado

**Verificar o cabo de rede:**
- Confira se o conector RJ-45 está firme na entrada do computador e na tomada da parede
- O LED na tomada de rede ou na placa de rede deve piscar — se apagado, o cabo pode estar danificado

**Diagnóstico pelo Windows:**
1. Clique com botão direito no ícone de rede (canto inferior direito) → "Diagnosticar problemas"
2. O Windows identifica se é problema de adaptador, cabo ou configuração

**Wi-Fi fraco (especialmente no barracão ou produção):**
- Afaste o computador de interferências (máquinas industriais, micro-ondas, outros rádios)
- Tente conectar ao ponto de acesso mais próximo (se houver mais de uma rede Wi-Fi disponível)
- Wi-Fi em ambientes industriais é mais instável que cabo — considere solicitar ponto de rede cabeado

---

### Wi-Fi vs Cabo — qual usar?

| Situação | Recomendado |
|----------|-------------|
| Computador fixo (desktop, all-in-one) | Cabo sempre |
| Notebook em escritório fixo | Cabo quando possível |
| Notebook em movimento / reunião | Wi-Fi |
| Barracão/galpão de produção | Cabo (Wi-Fi industrial requer avaliação do TI) |
| Home office | Wi-Fi ou cabo doméstico |

---

### Quando acionar o TI

- Nenhum dos passos acima resolve
- Vários computadores afetados ao mesmo tempo
- Wi-Fi de um setor inteiro está fraco ou ausente
- Precisa de novo ponto de rede cabeado instalado

**Informações para o chamado:**
- Setor e localização (sala, barracão, filial, andar)
- Quantas máquinas estão afetadas?
- Quando começou?
- É sem conexão total ou só muito lento?
- Cabo ou Wi-Fi? (ou os dois?)
- Resultado do diagnóstico do Windows (se tentou)
""",
    ),
    # ------------------------------------------------------------------
    Article(
        slug="monitor-configuracao-tela",
        title="Monitor e Configuração de Tela",
        tags=["monitor", "tela", "resolucao", "duplicar", "estender", "driver", "formatacao-tela", "segundo-monitor", "invertido"],
        body="""\
## Monitor e Configuração de Tela

---

### Telas trocadas / invertidas / na ordem errada

Se o mouse "pula" para o lado errado ao mover entre telas, ou a tela principal está invertida:

1. Clique com o botão direito na área de trabalho → **Configurações de Exibição**
2. Você verá a representação dos monitores (numerados 1, 2, etc.)
3. Clique em **"Identificar"** para ver qual número corresponde a qual tela física
4. **Arraste** o retângulo do monitor para a posição que corresponde à disposição física das telas na sua mesa
5. Clique em **"Aplicar"** → confirme se ficou correto

---

### Resolução incorreta / imagem borrada ou cortada

1. Clique com o botão direito na área de trabalho → Configurações de Exibição
2. Em "Resolução de Exibição", selecione a opção marcada como **(Recomendada)**
3. Se o monitor não está na lista ou a resolução recomendada parece errada, pode ser problema de driver de vídeo → acione o TI

---

### Segundo monitor não é reconhecido

**Verifique os cabos:**
- HDMI, DisplayPort ou VGA — confira se estão firmemente conectados nos dois lados
- Tente trocar de porta (se o computador tiver mais de uma saída de vídeo)

**Force a detecção:**
1. Configurações de Exibição → rolar até o final → clicar em **"Detectar"**
2. Ou use o atalho **Win + P** → selecione "Estender" para tentar ativar o segundo monitor

**Se ainda não aparecer:**
- Teste o monitor em outro computador — confirma se o monitor funciona
- Teste com outro cabo — cabos de vídeo podem falhar
- Acione o TI se o monitor for confirmado como funcional

---

### Modos de exibição (Win + P)

| Modo | Quando usar |
|------|------------|
| Somente tela do PC | Usar apenas o notebook (sem monitor externo) |
| Duplicar | Apresentações — mesma imagem nas duas telas |
| Estender | Trabalho com dois monitores (tela adicional independente) |
| Somente segunda tela | Monitor externo como principal (notebook fechado) |

Atalho rápido: **Win + P** abre o painel de seleção.

---

### Monitor sem imagem ao ligar

1. Verifique se o monitor está ligado (botão de energia no próprio monitor)
2. Confira o cabo de vídeo (HDMI/DisplayPort/VGA) — conecte firmemente
3. Verifique se o monitor está na entrada correta: botão "Input" ou "Source" no monitor
4. Ligue e desligue o monitor pelo botão de energia
5. Reinicie o computador

---

### Quando acionar o TI

- Monitor físico com defeito (tela preta, linhas, manchas)
- Driver de vídeo corrompido (tela piscando, artefatos visuais)
- Resolução ou taxa de atualização não ajustam corretamente
- Necessidade de instalar ou configurar terceiro monitor
- Monitor exibe mensagem "Sem sinal" mesmo com cabo e computador ligados e testados

**Informações para o chamado:** modelo do monitor (etiqueta atrás), tipo de cabo (HDMI, VGA, DisplayPort), número de patrimônio do computador, e se o problema é intermitente ou constante.
""",
    ),
]


async def main() -> None:
    sys.path.insert(0, "/app")

    from sqlalchemy import text as sa_text
    from app.services.rag import ingester
    from app.db.session import _Session  # noqa: PLC2701

    results: list[tuple[str, str, int | str]] = []

    async with _Session() as db:
        for art in ARTICLES:
            try:
                res = await db.execute(
                    sa_text(
                        "INSERT INTO helpdesk.kb_articles "
                        "(slug, title, tags, trust_level, created_by) "
                        "VALUES (:slug, :title, :tags, :trust, :created_by) "
                        "ON CONFLICT (slug) DO NOTHING RETURNING id"
                    ),
                    {
                        "slug": art.slug,
                        "title": art.title,
                        "tags": art.tags,
                        "trust": art.trust_level,
                        "created_by": SEED_USER_ID,
                    },
                )
                row = res.fetchone()
                if row is None:
                    results.append((art.slug, art.title, "SKIP"))
                    continue

                article_id = str(row.id)
                await db.execute(
                    sa_text(
                        "INSERT INTO helpdesk.kb_article_versions "
                        "(article_id, version, body_markdown, edited_by) "
                        "VALUES (CAST(:aid AS uuid), 1, :body, :edited_by)"
                    ),
                    {"aid": article_id, "body": art.body, "edited_by": SEED_USER_ID},
                )
                await db.commit()

                chunks = await ingester.ingest_article(article_id, db)
                results.append((art.slug, art.title, chunks))

            except Exception as exc:
                await db.rollback()
                results.append((art.slug, art.title, f"ERRO: {exc}"))

    # Print result table
    print()
    print(f"{'Slug':<40} {'Chunks':>6}  Título")
    print("-" * 90)
    ok = fail = skip = 0
    for slug, title, chunks in results:
        if isinstance(chunks, int):
            print(f"{slug:<40} {chunks:>6}  {title}")
            ok += 1
        elif chunks == "SKIP":
            print(f"{slug:<40} {'SKIP':>6}  {title}")
            skip += 1
        else:
            print(f"{slug:<40} {'FAIL':>6}  {chunks}")
            fail += 1

    print("-" * 90)
    print(f"Total: {ok} OK  {skip} já existiam  {fail} falhou  de {len(ARTICLES)} artigos\n")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
