"""Seed KB v2 — artigos baseados em chamados reais de helpdesk.

Run inside the backend container:
    docker exec helpdesk-backend python /app/scripts/seed_kb_v2.py

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
        slug="impressoras-troubleshooting",
        title="Impressoras — Resolução de Problemas (Jato de Tinta, Produção, Zebra)",
        tags=["impressora", "jato-de-tinta", "zebra", "producao", "offline", "tinta", "driver"],
        body="""## Impressoras — Resolução de Problemas

Guia para os três tipos mais comuns: impressora de jato de tinta de escritório, impressora de produção e Zebra (etiquetas).

---

### 1. Impressora Jato de Tinta — Tinta Preta Acabou / Nível Baixo

**Sintomas:** Impressão saindo branca, apagada ou com listras; alerta "tinta preta baixa", "substituir cartucho" ou ícone vermelho na barra de tarefas.

**O que tentar antes de acionar o TI:**
1. Abra o software de status da impressora (ícone na barra de tarefas ou Painel de Controle → Dispositivos e Impressoras → clique direito → Preferências de Impressão)
2. Confirme qual cartucho está vazio — preto (Black / BK) ou colorido (C/M/Y)
3. **Modelos com tanque externo (EcoTank, MegaTank):** o refil pode ser feito diretamente. Verifique se há garrafa de tinta reserva no TI ou no almoxarifado. Abra a tampa do tanque e complete até a linha máxima
4. **Modelos com cartucho:** solicite ao TI o número do modelo impresso no cartucho atual (ex.: HP 664, Canon PG-110) para buscar o reserva
5. Cartucho quase vazio? Remova-o, agite suavemente na horizontal e recoloque — rende mais alguns documentos emergenciais

**Quando acionar o TI:** Não há estoque; cartucho foi trocado mas erro persiste; alerta de "cabeça de impressão"; impressora não reconhece o cartucho novo.

---

### 2. Impressora de Produção — Não Imprime / Offline

**Sintomas:** Trabalho enviado mas não sai; impressora aparece como "Offline"; LED piscando; erro no painel.

**O que tentar antes de acionar o TI:**
1. **Reinicie a impressora:** desligue pelo botão, aguarde 30 s, ligue novamente — aguarde ela inicializar completamente
2. **Limpe a fila de impressão:**
   - Win + R → `services.msc` → localize "Spooler de Impressão" → clique direito → Reiniciar
   - Ou: Painel de Controle → Dispositivos e Impressoras → clique direito na impressora → "Ver o que está imprimindo" → cancele todos os trabalhos
3. **Impressora aparece "Offline":** clique direito na impressora → menu Impressora → desmarque "Usar impressora offline"
4. Verifique cabo de rede ou USB — recoloque firmemente. Se for rede, tente pingar o IP da impressora (Prompt → `ping <IP>`)
5. Confirme que não há atolamento de papel: abra todas as tampas e verifique o caminho do papel
6. Defina como impressora padrão: clique direito → "Definir como padrão"

**Quando acionar o TI:** Nenhuma das etapas resolve; erro de atolamento preso no mecanismo interno; impressora não reconhecida pelo computador; necessidade de reinstalar driver.

---

### 3. Impressora Zebra (Etiquetas) — Não Conecta / Não Imprime

**Sintomas:** Software não detecta a Zebra; etiquetas não saem; LED laranja ou vermelho; ZPL enviado sem resposta.

**O que tentar antes de acionar o TI:**
1. Desligue e religue a Zebra pelo botão de energia (aguarde LED verde estável)
2. Conecte o cabo USB diretamente ao computador — evite hubs USB intermediários
3. **Calibração de mídia** (passo mais comum que resolve): com a impressora ligada, pressione e segure o botão **Feed** por ~2 s até ouvir avanço de etiqueta — isso recalibra a detecção do rolo
4. Teste de auto-diagnóstico: pressione **Feed** com a tampa fechada — a Zebra deve imprimir uma etiqueta de configuração com IP e versão de firmware
5. Verifique no software (Bartender, ZDesigner, ZPL Viewer) se a impressora selecionada é a Zebra correta e a porta (USB ou porta de rede) está correta
6. Gerenciador de Dispositivos (Win + X → Gerenciador de Dispositivos): se houver símbolo de exclamação amarelo, reinstale o driver ZDesigner (disponível em zebra.com ou solicitando ao TI)

**Quando acionar o TI:** Driver não instala; necessidade de configurar IP fixo; LED vermelho persistente (falha de hardware); impressora funciona standalone mas não pelo sistema.
""",
    ),
    # ------------------------------------------------------------------
    Article(
        slug="sharepoint-pastas-acesso",
        title="SharePoint e Pastas de Rede — Sem Acesso / Não Consegue Mover ou Salvar",
        tags=["sharepoint", "pasta-rede", "acesso", "permissao", "drive", "comex", "repense", "mover", "salvar"],
        body="""## SharePoint e Pastas de Rede — Acesso e Permissões

Cobre problemas de acesso ao SharePoint (portal web e OneDrive) e a pastas de rede mapeadas (drives compartilhados por departamento ou programa).

---

### Sintomas comuns

- Mensagem "Acesso negado" ou "Você não tem permissão para acessar esta pasta"
- Pasta abre mas não permite salvar, mover ou criar arquivos (somente leitura)
- Drive mapeado (ex.: Z:, W:, letra de rede) desaparece ou aparece com X vermelho
- SharePoint retorna erro 403 ou página em branco ao tentar abrir documentos

---

### O que tentar antes de acionar o TI

**Para pastas de rede mapeadas (\\\\servidor\\pasta):**
1. Clique com o botão direito no drive com X vermelho → "Desconectar unidade de rede" → em seguida, "Mapear unidade de rede" com o mesmo caminho
2. Confirme que está na rede corporativa ou conectado via VPN (fora do escritório)
3. Tente acessar o caminho diretamente: Win + R → cole o caminho UNC (ex.: `\\\\servidor\\comex`) → Enter
4. Faça logoff e logon no Windows — credenciais de rede podem ter expirado após troca de senha

**Para SharePoint (portal web):**
1. Limpe cache e cookies do navegador (Ctrl + Shift + Del → "Todos os tempos")
2. Tente em modo anônimo (Ctrl + Shift + N no Chrome) — descarta conflitos de cookies
3. Confirme que está logado com a conta corporativa (não pessoal) no Microsoft 365
4. Verifique se o link compartilhado não expirou — links de documentos enviados por e-mail têm validade definida pelo remetente

**Para erro "não consigo mover ou salvar arquivos":**
1. Verifique se o arquivo está aberto por outra pessoa — aparece bloqueado com ícone de cadeado no SharePoint
2. Confirme que a pasta de destino não está marcada como somente leitura: clique direito na pasta → Propriedades → desmarque "Somente leitura" (se disponível)
3. Tente salvar com outro nome (Salvar Como) — descarta bloqueio de arquivo em uso
4. No SharePoint, confirme que seu perfil tem permissão de "Editar" e não apenas "Leitura"

---

### Quando acionar o TI

- Nenhuma das etapas resolve
- Precisa de acesso a pasta de novo programa ou projeto (ex.: Repense, Comex, novos departamentos)
- Usuário recém-admitido ou que mudou de área e não tem acesso à pasta correspondente
- Arquivo ou pasta sumiu (possível exclusão acidental — TI pode recuperar via backup ou lixeira do SharePoint)

**Informações para passar ao TI:** caminho completo da pasta (ex.: `\\\\srv-files\\comercial\\comex`) ou URL do SharePoint, mensagem de erro exata, e-mail do responsável pela pasta para liberação de permissão.
""",
    ),
    # ------------------------------------------------------------------
    Article(
        slug="sap-b1-erros-comuns",
        title="SAP B1 — Erros Comuns (Senha Congelada, Nenhum Registro Concordante)",
        tags=["sap", "autosky", "senha", "bloqueio", "transferencia", "estoque", "nenhum-registro", "concordante"],
        body="""## SAP B1 — Erros Comuns

Guia para os dois erros mais reportados no SAP Business One acessado via Autosky.

---

### 1. Senha Congelada / Usuário Bloqueado Após Troca de Senha

**Sintomas:**
- Após troca de senha obrigatória, o SAP retorna "Usuário bloqueado" ou "Senha inválida"
- Mensagem "Usuário está bloqueado, contate o administrador"
- A senha nova não é aceita mesmo sendo digitada corretamente

**Por que acontece:**
O SAP B1 gerencia a senha internamente — ela **não sincroniza automaticamente** com a senha de domínio do Windows. Ao trocar a senha do domínio, a senha do SAP permanece a anterior. Tentativas erradas de login (digitando a nova senha do domínio no SAP) causam o bloqueio.

**O que fazer:**
1. **Não tente mais combinações** — cada tentativa errada agrava o bloqueio
2. Entre em contato com o TI informando seu usuário SAP (geralmente igual ao login de rede)
3. O TI irá desbloquear o usuário e resetar a senha diretamente no console do SAP B1
4. Após desbloqueio, você receberá uma senha temporária — troque-a no **primeiro login** pelo menu SAP → Administração → Redefinir Senha

**Prevenção:**
- A troca de senha no SAP é feita dentro do próprio sistema (menu SAP), separadamente da senha de domínio
- Se receber aviso de "senha expirará em X dias", troque-a dentro do SAP antes do vencimento

---

### 2. Erro "Nenhum Registro Concordante Encontrado" (Transferência de Estoque / NF / Pedido)

**Sintomas:**
- Ao tentar confirmar uma Transferência de Estoque, Nota Fiscal de Saída ou Pedido de Compra, SAP retorna: **"Nenhum registro concordante encontrado"**
- O sistema não permite adicionar o documento

**Causas mais comuns e o que verificar:**

| Causa | Como verificar | Ação |
|-------|---------------|------|
| Depósito de origem ou destino não está ativo | SAP → Estoque → Depósitos → verifique se o depósito está marcado como ativo | Acionar TI para ativar |
| Código de item inativo ou sem estoque no depósito | Verificar ficha do item: SAP → Estoque → Dados do Item | Confirmar saldo de estoque antes da transferência |
| Regra de contabilidade não mapeada para o par depósito/conta | Erro frequente em novos depósitos ou filiais | Acionar TI/controller para mapear conta |
| Série de numeração de documento esgotada ou bloqueada | SAP → Administração → Definições do Sistema → Séries de Numeração | Acionar TI para renovar série |
| Data de lançamento fora do período aberto | Verificar se a data do documento está dentro do período fiscal aberto | Corrigir data ou solicitar abertura de período |

**O que fazer:**
1. Anote o código do item, depósito de origem e destino, e data do documento
2. Tente verificar as causas acima antes de acionar o TI
3. Se não conseguir identificar: abra chamado no helpdesk com **print da tela do erro + código do documento tentado**

**Informações para o TI:** código do item, origem → destino da transferência, data, mensagem exata de erro e print de tela.
""",
    ),
    # ------------------------------------------------------------------
    Article(
        slug="teams-atualizacao-bloqueio",
        title="Microsoft Teams — Não Abre por Atualização Pendente",
        tags=["teams", "microsoft", "atualizacao", "update", "reuniao", "nao-abre"],
        body="""## Microsoft Teams — Não Abre por Atualização Pendente

**Sintomas:** Teams abre uma tela pedindo atualização e fecha em seguida; mensagem "Uma atualização está disponível" e o app não prossegue; tela de loading infinita.

---

### Solução Imediata (reunião em menos de 10 minutos)

**Use o Teams pelo navegador — funciona sem instalação:**
1. Abra o Chrome ou Edge
2. Acesse: **teams.microsoft.com**
3. Faça login com sua conta corporativa
4. Clique em "Usar o aplicativo web" quando perguntado
5. Todas as funcionalidades de reunião, chat e chamada estão disponíveis na versão web

---

### Solução Definitiva (resolver o problema de atualização)

**Opção A — Deixar o Teams atualizar:**
1. Feche o Teams completamente (clique no ícone da bandeja do sistema → clique direito → Fechar)
2. Aguarde 2 a 5 minutos para a atualização baixar em segundo plano
3. Reabra o Teams normalmente
4. Se aparecer o botão "Atualizar agora", clique e aguarde

**Opção B — Forçar atualização manual:**
1. Feche o Teams completamente
2. Pressione Win + R → cole: `%localappdata%\\Microsoft\\Teams\\Update.exe --processStart Teams.exe`
3. Aguarde o processo de atualização concluir

**Opção C — Limpar cache do Teams (quando as opções A e B falham):**
1. Feche o Teams completamente
2. Win + R → cole: `%appdata%\\Microsoft\\Teams`
3. Apague as pastas: **Cache**, **blob_storage**, **databases**, **GPUCache**, **IndexedDB**, **Local Storage**, **tmp**
4. Reabra o Teams — ele irá reconfigurar (pode pedir login novamente)

---

### Quando acionar o TI

- Teams não abre mesmo após limpar o cache
- Erro de permissão ao tentar apagar pastas do cache
- Computador sem permissão de administrador para executar a atualização
- Versão do Teams incompatível com a política corporativa (TI fará reinstalação)
""",
    ),
    # ------------------------------------------------------------------
    Article(
        slug="adobe-troubleshooting",
        title="Adobe — Parou de Funcionar (Acrobat, Reader, Creative Cloud)",
        tags=["adobe", "acrobat", "reader", "pdf", "creative-cloud", "licenca", "nao-abre"],
        body="""## Adobe — Parou de Funcionar

Cobre os produtos mais comuns: Adobe Acrobat Reader (leitura de PDF), Adobe Acrobat (edição de PDF) e produtos Creative Cloud (Photoshop, Illustrator, etc.).

---

### Sintomas e Causas Comuns

- Aplicativo não abre ou fecha logo após iniciar
- Erro "Adobe Acrobat não está licenciado para uso"
- Mensagem de licença expirada ou "Entrar para continuar"
- PDF abre em branco ou com erro de renderização
- Creative Cloud mostra "Acesso negado" ou pede renovação de assinatura

---

### Adobe Acrobat Reader (leitura de PDF gratuita)

**O que tentar:**
1. Feche o processo no Gerenciador de Tarefas: Ctrl + Alt + Del → Gerenciador de Tarefas → localize "AcroRd32.exe" ou "Acrobat.exe" → Finalizar Tarefa
2. Reabra o Reader normalmente
3. Se aparecer aviso de atualização: Help → Verificar atualizações → deixe atualizar
4. PDF não abre corretamente: clique direito no arquivo → Abrir com → Adobe Acrobat Reader (pode estar abrindo no navegador em vez do Reader)
5. Reinstale se corrompido: Painel de Controle → Programas → Adobe Acrobat Reader DC → Reparar

---

### Adobe Acrobat (edição de PDF — licença corporativa)

**O que tentar:**
1. Se pedir login: entre com a conta Microsoft corporativa (SSO) — **não** crie conta pessoal Adobe
2. Erro de licença: Help → Desativar → faça logout → entre novamente com a conta corporativa
3. Tente em modo offline: Help → Preferências → desmarque "Verificar conexão online ao iniciar"
4. Se mensagem de "computador atingiu limite de ativações": acionar TI — a licença permite até 2 dispositivos por usuário

---

### Adobe Creative Cloud (Photoshop, Illustrator, InDesign, etc.)

**O que tentar:**
1. Abra o **Creative Cloud Desktop** (ícone no canto inferior direito) — verifique se o app específico está instalado e atualizado
2. Faça logout e login novamente no Creative Cloud: ícone CC → foto do perfil → Sair → entrar com conta corporativa
3. Se o Creative Cloud Desktop não abre: Gerenciador de Tarefas → finalize processos "Creative Cloud" → reabra pelo menu Iniciar
4. Erro persistente de licença: o TI precisa verificar se a licença foi atribuída corretamente no Admin Console da Adobe

---

### Quando acionar o TI

- Erro de licença persiste após logout/login
- Software não instalado no computador (precisa ser adicionado pelo TI via Adobe Admin Console)
- Erro de instalação ou atualização que não resolve
- Usuário precisar de produto Adobe que não usa atualmente (verificar se há licença disponível)

**Informação útil para o TI:** nome exato do produto Adobe, versão instalada (Help → Sobre) e mensagem de erro completa.
""",
    ),
    # ------------------------------------------------------------------
    Article(
        slug="download-bloqueado",
        title="Download Bloqueado — Sistema Não Completa o Download",
        tags=["download", "bloqueio", "antivirus", "smartscreen", "seguranca", "navegador", "firewall"],
        body="""## Download Bloqueado — Sistema Não Completa o Download

**Sintomas:** Download inicia mas é interrompido automaticamente; mensagem "Este arquivo pode ser perigoso" no Chrome/Edge; alerta do antivírus ao tentar baixar; Windows SmartScreen bloqueia a execução do instalador.

---

### Por que o download é bloqueado?

A infraestrutura de TI aplica múltiplas camadas de proteção:
1. **Antivírus corporativo** (endpoint) — bloqueia arquivos com assinaturas suspeitas
2. **Windows SmartScreen** — bloqueia executáveis não assinados digitalmente
3. **Proxy/Firewall** — bloqueia URLs de download não categorizadas como seguras
4. **Navegador** — Chrome e Edge têm proteção contra downloads maliciosos embutida

---

### O que verificar e tentar

**Passo 1 — Identifique a camada que bloqueou:**
- Mensagem no canto inferior do Chrome/Edge? → É o navegador
- Popup do antivírus (Trend Micro, Symantec, etc.)? → É o endpoint
- Janela azul "Windows protegeu seu PC"? → É o SmartScreen
- Download nem começou? → É o proxy/firewall

**Passo 2 — Tente o contorno básico:**
- **Navegador:** clique nas reticências (...) ao lado do arquivo bloqueado na lista de downloads → "Manter mesmo assim" (apenas se você tem certeza que é seguro)
- **SmartScreen (executável):** clique em "Mais informações" → "Executar assim mesmo" — **só faça isso se o arquivo foi solicitado pelo TI ou é de fornecedor confiável**
- Tente baixar em outro navegador (Edge em vez de Chrome ou vice-versa)

**Passo 3 — Documentar para o TI:**
- Nome e URL completa de onde está tentando baixar
- Nome do fornecedor ou sistema (ex.: "sistema de seguro agrícola da SegurosXYZ")
- Print do erro exato

---

### Quando acionar o TI (obrigatório nesses casos)

- O arquivo é legítimo e necessário para o trabalho mas o antivírus não libera
- Proxy bloqueou o site de download — o TI pode fazer whitelist temporária
- Download precisa de permissão de administrador para instalar
- Instalador bloqueado por política de grupo (GPO) — só o TI pode liberar

**Importante:** não tente desabilitar o antivírus ou burlar o proxy por conta própria. O TI avalia o risco e faz a liberação controlada com registro.
""",
    ),
    # ------------------------------------------------------------------
    Article(
        slug="qlik-sense-relatorios",
        title="Qlik Sense — Filtros, Relatórios e Solicitações de Ajuste",
        tags=["qlik", "qlik-sense", "relatorio", "filtro", "dashboard", "bi", "analise", "estoque"],
        body="""## Qlik Sense — Filtros, Relatórios e Solicitações de Ajuste

O Qlik Sense é a plataforma de BI (Business Intelligence) utilizada para análise de dados. Este artigo cobre tanto problemas técnicos de acesso quanto solicitações de melhorias nos relatórios.

---

### Problemas Técnicos de Acesso

**Não consigo acessar um painel / dashboard:**
1. Confirme que está usando o link correto — o TI ou o responsável pelo painel deve ter enviado a URL
2. Faça logout e login novamente com a conta corporativa
3. Limpe o cache do navegador (Ctrl + Shift + Del)
4. Se o painel foi compartilhado recentemente, aguarde até 15 minutos para a permissão propagar

**Dados do relatório não estão atualizados:**
- O Qlik carrega dados em janelas de atualização programadas (geralmente diária, no início da manhã ou à noite)
- Verifique no rodapé ou cabeçalho do painel a data/hora da última atualização
- Se os dados estiverem desatualizados por mais de 24 h: acione o TI informando o nome exato do painel

**Filtros existentes não funcionam ou travam:**
1. Clique em "Limpar todas as seleções" (borracha no menu superior) para resetar os filtros
2. Feche e reabra o painel
3. Tente em outro navegador

---

### Solicitação de Novo Filtro ou Ajuste em Relatório Existente

**Esta é uma solicitação de desenvolvimento, não um incidente de suporte.**

Solicitar um novo filtro, campo ou visualização em um painel Qlik existente envolve:
1. Levantamento dos requisitos pelo TI/BI
2. Desenvolvimento e testes no ambiente de homologação
3. Publicação em produção

**SLA estimado:** 5 a 10 dias úteis dependendo da complexidade e da fila de solicitações de BI.

**Como solicitar corretamente (inclua no chamado):**
- Nome exato do painel / app Qlik (ex.: "Análise de Estoques — Filial Sul")
- O que precisa ser incluído: descrição do filtro ou campo (ex.: "filtro por fornecedor — campo 'CardName' da tabela de compras")
- Período de dados relevante (se aplicável)
- Justificativa de negócio (para priorização)
- Quem mais usaria esse filtro (usuários ou área impactada)

**Importante:** alterações em painéis compartilhados afetam todos os usuários — o TI avalia o impacto antes de publicar.

---

### Quando acionar o TI

- Acesso negado mesmo após logout/login
- Painel sumiu da lista de apps
- Dados claramente incorretos (ex.: valores zerados onde não deveriam estar)
- Solicitação formal de novo filtro, campo ou painel
""",
    ),
    # ------------------------------------------------------------------
    Article(
        slug="hardware-solicitacao-periferico",
        title="Hardware — Solicitação de Periférico (Teclado, Mouse, Headset, Monitor)",
        tags=["hardware", "periferico", "teclado", "mouse", "headset", "monitor", "notebook", "solicitacao", "patrimonio"],
        body="""## Hardware — Solicitação de Periférico

Guia para solicitação de equipamentos periféricos: teclado, mouse, headset, monitor, webcam, adaptadores, etc.

---

### Tipos de Solicitação

| Tipo | Exemplos | Quem aprova |
|------|----------|-------------|
| Reposição de periférico danificado | Teclado quebrado, mouse não funciona | TI (analisa e repõe do estoque) |
| Novo periférico para funcionário existente | Headset para home office, monitor adicional | Gestor direto + TI |
| Periférico para novo colaborador / aprendiz | Kit teclado + mouse para onboarding | Gestor + RH + TI |
| Upgrade de equipamento | Trocar notebook antigo por modelo mais novo | Gestor + TI + Diretoria |

---

### Como Solicitar

**Para reposição de item danificado:**
1. Abra chamado no helpdesk descrevendo o periférico com defeito (modelo se souber, sintoma)
2. TI verifica o estoque disponível — se houver, a entrega ocorre em até 2 dias úteis
3. O item danificado deve ser devolvido ao TI para descarte ou envio à assistência

**Para novo periférico (funcionário existente):**
1. Solicite aprovação do seu gestor direto por e-mail (print ou encaminhe ao TI)
2. Abra chamado no helpdesk com: tipo de periférico, justificativa, e-mail do gestor que aprovou
3. TI verifica estoque e, se não houver, abre processo de compra

**Para periférico de novo colaborador / aprendiz:**
1. O gestor ou RH abre o chamado com: nome do colaborador, cargo, data de início, lista de equipamentos necessários
2. Inclua se o colaborador já tem computador ou se precisa de estação completa
3. TI prepara o kit de onboarding no prazo acordado (ideal: 3 dias úteis antes do início)

---

### Informações Necessárias no Chamado

- **Quem precisa:** nome completo do colaborador
- **O que precisa:** tipo de periférico (teclado, mouse, headset com microfone, etc.)
- **Por quê:** reposição de item danificado, novo usuário, mudança de função
- **Para quando:** data necessária (urgência real)
- **Local de entrega:** sala, setor, filial

---

### Periférico Pessoal x Corporativo

- Periféricos solicitados são patrimônio da empresa — devolvidos em caso de desligamento
- Periféricos pessoais trazidos de casa podem ser usados por conta do colaborador, mas o TI não oferece suporte para equipamentos não corporativos
- Em caso de dúvida sobre o que é de patrimônio da empresa, o TI pode consultar o inventário pelo número de registro do equipamento

---

### Quando acionar o TI

- Periférico corporativo apresentou defeito
- Onboarding de novo colaborador sem kit de trabalho
- Mudança de posto de trabalho exige realocação de equipamentos
""",
    ),
    # ------------------------------------------------------------------
    Article(
        slug="itau-corporativo-app",
        title="Aplicativo Itaú Corporativo — Erro de Conexão / Não Abre",
        tags=["itau", "banco", "corporativo", "app", "token", "certificado", "conexao", "erro"],
        body="""## Aplicativo Itaú Corporativo — Erro de Conexão / Não Abre

**Sintomas:**
- Aplicativo fica em loop de "verificando" ou "carregando" sem abrir
- Mensagem de erro: **"An error occurred while processing your request"**
- Erro de certificado ou "conexão não segura"
- App abre mas não exibe saldo ou movimentações
- Login retorna "usuário ou senha inválidos" mesmo com credenciais corretas

---

### O que tentar antes de acionar o TI

**Passo 1 — Reinicie o serviço do aplicativo:**
1. Feche completamente o aplicativo (Gerenciador de Tarefas → finalize todos os processos relacionados ao Itaú)
2. Aguarde 30 segundos
3. Reabra o aplicativo

**Passo 2 — Verifique a versão do aplicativo:**
1. No próprio app: menu de configurações ou "Sobre" → veja a versão instalada
2. Se houver atualização disponível, instale — muitos erros de conexão são resolvidos com atualização

**Passo 3 — Verifique data e hora do computador:**
- Certificados digitais são sensíveis à hora do sistema
- Clique no relógio do Windows → "Ajustar data e hora" → confirme que está correto e sincronize com servidor de tempo

**Passo 4 — Verifique conexão de rede:**
- Confirme que está na rede corporativa ou com VPN ativa (se necessário para acesso bancário)
- Tente abrir outro site para confirmar que a internet funciona

**Passo 5 — Limpe o cache/dados do aplicativo:**
- Painel de Controle → Programas → localize o Itaú Corporativo → Reparar ou Desinstalar e reinstalar
- Ou: localize a pasta de dados do app em `%appdata%` e apague os arquivos de cache

**Passo 6 — Verifique certificado digital:**
- Se o acesso usa certificado A1 ou A3: confirme que o certificado não expirou
- Para certificado A3 (token físico): verifique se o token está conectado e o driver instalado

---

### Quando acionar o TI (e o que informar)

- Nenhum dos passos acima resolve
- Erro persiste após reinstalação do aplicativo
- Certificado digital expirado — o TI auxilia no processo de renovação junto ao banco
- Acesso bloqueado pelo banco (limite de tentativas de login)

**Para o TI:** informe o erro exato (print de tela), versão do aplicativo e se o problema ocorre em todos os computadores ou apenas no seu.

**Para questões de senha bancária ou permissões de acesso:** contate diretamente o responsável financeiro ou o gestor da conta junto ao Itaú Empresas — o TI resolve a parte técnica, não credenciais bancárias.
""",
    ),
    # ------------------------------------------------------------------
    Article(
        slug="pia-metas-acesso",
        title="PIA / Metas — Problemas de Acesso ao Sistema",
        tags=["pia", "metas", "rh", "desempenho", "acesso", "login", "nao-carrega"],
        body="""## PIA / Metas — Problemas de Acesso

Sistema de gestão de desempenho individual. Este artigo foca nos problemas de acesso relatados com maior frequência.

---

### Sintomas

- Tela de login aparece mas não aceita as credenciais
- Página não carrega ou fica em branco
- Acesso funciona na rede corporativa mas não de casa
- Usuário não encontrado no sistema

---

### O que tentar

**Problema: login não funciona**
1. Use o usuário de rede (ex.: `joao.silva`) — **sem** o sufixo @empresa.com
2. A senha do PIA é a mesma do domínio corporativo; se trocou recentemente, use a nova senha
3. Se a senha do domínio expirou, redefina pelo portal de autoatendimento corporativo primeiro

**Problema: página não carrega / tela branca**
1. Limpe o cache do navegador: Ctrl + Shift + Del → "Todo o período" → marque cache e cookies → Limpar
2. Desative extensões do navegador (ad-blockers podem interferir)
3. Tente em modo anônimo (Ctrl + Shift + N) ou em outro navegador
4. Verifique se JavaScript está habilitado no navegador

**Problema: acesso fora da empresa**
- O sistema pode exigir VPN ativa para ser acessado externamente
- Conecte à VPN corporativa (OpenVPN) antes de tentar acessar
- Se não tem VPN configurada, abra chamado no TI para instalação

**Problema: usuário não encontrado**
- Para colaboradores novos: o RH precisa criar o cadastro antes do TI liberar acesso
- Para colaboradores que mudaram de área: o RH atualiza o perfil

---

### Quando acionar

| Problema | Quem acionar |
|----------|-------------|
| Login não funciona / senha incorreta | TI (reset de senha de domínio) |
| Usuário não existe no sistema | RH (criação de cadastro) |
| Não vejo minhas metas ou período errado | Gestor direto / RH |
| Erro técnico (tela branca, 500, etc.) | TI |
| Prazo de avaliação está fechado | RH |
""",
    ),
]


async def main() -> None:
    import os
    sys.path.insert(0, "/app")

    from sqlalchemy import text as sa_text
    from app.services.rag import ingester
    from app.db.session import _Session  # noqa: PLC2701

    ok = 0
    failed = 0

    async with _Session() as db:
        for art in ARTICLES:
            try:
                res = await db.execute(
                    sa_text(
                        "INSERT INTO helpdesk.kb_articles "
                        "(slug, title, tags, trust_level, created_by) "
                        "VALUES (:slug, :title, :tags, :trust, :created_by) "
                        "ON CONFLICT (slug) DO NOTHING "
                        "RETURNING id"
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
                    print(f"  [SKIP] {art.slug} — já existe")
                    ok += 1
                    continue

                article_id = str(row.id)

                await db.execute(
                    sa_text(
                        "INSERT INTO helpdesk.kb_article_versions "
                        "(article_id, version, body_markdown, edited_by) "
                        "VALUES (CAST(:aid AS uuid), 1, :body, :edited_by)"
                    ),
                    {
                        "aid": article_id,
                        "body": art.body,
                        "edited_by": SEED_USER_ID,
                    },
                )
                await db.commit()

                chunks = await ingester.ingest_article(article_id, db)
                print(f"  [OK]   {art.slug} — {chunks} chunk(s)")
                ok += 1

            except Exception as exc:
                await db.rollback()
                print(f"  [FAIL] {art.slug} — {exc}")
                failed += 1

    print(f"\nTotal: {ok} OK, {failed} falhou de {len(ARTICLES)} artigos.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
