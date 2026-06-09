"""Seed script — populates helpdesk.kb_articles with the initial KB content.

Run inside the backend container:
    docker exec helpdesk-backend python /app/scripts/seed_kb.py

Idempotent: uses ON CONFLICT (slug) DO NOTHING so safe to re-run.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# KB articles
# ---------------------------------------------------------------------------

@dataclass
class Article:
    slug: str
    title: str
    tags: list[str]
    body: str
    trust_level: str = "internal_published"


ARTICLES: list[Article] = [
    Article(
        slug="trocar-senha-portal",
        title="Trocar Senha (Portal Corporativo)",
        tags=["senha", "portal", "acesso", "dominio"],
        body="""## Trocar Senha (Portal Corporativo)

**O que é:** Portal de autoatendimento para redefinição e troca de senha da conta corporativa (rede/e-mail/domínio).

**Acesso:** Acessível pelo navegador sem necessidade de estar conectado à VPN. Disponível na intranet ou pelo endereço informado pelo TI no onboarding.

**Problemas comuns:**

- Não consigo acessar o portal de troca de senha → Verifique se o navegador está atualizado; tente limpar cache e cookies (Ctrl+Shift+Del); se usar Internet Explorer, migre para Chrome ou Edge
- Meu link de redefinição expirou → Solicite um novo link; links têm validade de 24 horas
- Troquei a senha mas o e-mail / computador não aceita → Aguarde 5 minutos para sincronização e faça logoff/logon; em computadores físicos, pressione Ctrl+Alt+Del → "Trocar usuário"
- Conta bloqueada após várias tentativas → Contate o TI para desbloqueio manual; não tente mais combinações pois o bloqueio pode se estender
- Não recebi o e-mail de confirmação → Verifique pasta de spam; confirme com o TI se o e-mail cadastrado está correto

**Quem contatar se não resolver:** TI (helpdesk interno ou ramal interno)
""",
    ),
    Article(
        slug="pia-metas-anuais",
        title="PIA / Metas Anuais",
        tags=["pia", "metas", "rh", "desempenho"],
        body="""## PIA / Metas Anuais

**O que é:** Plataforma de gestão de desempenho individual (PIA — Plano Individual de Atividades) onde colaboradores registram e acompanham metas anuais definidas com seus gestores.

**Acesso:** Acesso via intranet corporativa ou link disponibilizado pelo RH. Requer login com credenciais corporativas. Conexão VPN pode ser necessária fora da rede.

**Problemas comuns:**

- Não consigo fazer login → Confirme que está usando o usuário de rede (sem @dominio); tente redefinir a senha pelo portal corporativo
- Não vejo minhas metas cadastradas → Verifique se está no ciclo/período correto (ano vigente); metas são cadastradas pelo gestor — acione-o para confirmação
- Tela em branco ou sistema não carrega → Limpe o cache do navegador; desative extensões (ad-blockers podem bloquear conteúdo); use Chrome ou Edge atualizados
- Não consigo salvar/editar minha avaliação → Confirme se o período de avaliação está aberto; fora da janela de edição o sistema fica somente leitura
- Não tenho acesso à plataforma → Solicite ao RH a criação ou reativação do usuário

**Quem contatar se não resolver:** RH (para permissões e cadastro) / TI (para falhas técnicas de acesso)
""",
    ),
    Article(
        slug="akronus-rh",
        title="Akronus (RH)",
        tags=["akronus", "rh", "ponto", "holerite", "ferias"],
        body="""## Akronus (RH)

**O que é:** Sistema de Recursos Humanos utilizado para gestão de ponto eletrônico, holerites, férias, afastamentos e dados cadastrais dos colaboradores.

**Acesso:** Acesso via navegador pela intranet. **Importante: a senha do Akronus é gerenciada exclusivamente pelo RH** — o TI não tem acesso a ela e não pode realizar reset.

**Problemas comuns:**

- Esqueci minha senha → Contate diretamente o RH para redefinição; o TI não gerencia esse acesso
- Conta bloqueada → Acione o RH com urgência para desbloqueio; não tente adivinhar a senha
- Não consigo visualizar meu holerite → Confirme o mês/ano selecionado; se o holerite não foi processado ainda, aguarde a data de fechamento da folha informada pelo RH
- Meu ponto está incorreto → Registre a ocorrência com seu gestor e acione o RH para ajuste manual
- Não tenho acesso ao sistema → Solicite ao RH a criação do usuário — novo acesso depende do cadastro de RH estar ativo
- Tela trava ou não carrega → Atualize o navegador; o Akronus pode requerer Java — consulte o TI para verificar compatibilidade

**Quem contatar se não resolver:** RH (qualquer questão de senha, acesso ou dados) / TI (apenas para erros técnicos de rede ou browser)
""",
    ),
    Article(
        slug="budget-campo",
        title="Budget Campo",
        tags=["budget", "campo", "financeiro", "despesas", "territorio"],
        body="""## Budget Campo

**O que é:** Ferramenta de gestão e acompanhamento de orçamento destinada às equipes de campo (representantes, supervisores e gerentes regionais), permitindo controle de despesas e verbas por território.

**Acesso:** Acesso via intranet ou aplicativo específico. Requer VPN quando acessado fora da rede corporativa. Perfis de acesso são definidos pelo gestor da área.

**Problemas comuns:**

- Não consigo fazer login → Use as credenciais corporativas (usuário de rede); se for primeiro acesso, solicite ao gestor a liberação do perfil
- Não vejo meu território/região no sistema → Verifique com seu gestor se o território foi corretamente atribuído ao seu usuário
- Não consigo lançar despesas → Confirme se o período orçamentário está aberto; verifique se seu perfil tem permissão de edição
- Saldo exibido está incorreto → Aguarde a atualização diária do sistema (geralmente no início da manhã); se persistir, acione o TI com print da tela e data
- Relatório não gera / exportação falha → Tente em outro navegador; para exportações em Excel, confirme que o Excel está instalado
- Não tenho acesso a determinada funcionalidade → Solicite ao gestor a revisão do perfil de acesso

**Quem contatar se não resolver:** TI (erros técnicos) / Gestor da área (permissões e perfis) / Controladoria (questões orçamentárias)
""",
    ),
    Article(
        slug="sap-b1-acesso-autosky",
        title="SAP B1 — Acesso (Autosky)",
        tags=["sap", "autosky", "erp", "acesso", "sessao-remota"],
        body="""## SAP B1 — Acesso (Autosky)

**O que é:** O SAP Business One é o ERP corporativo. O acesso é feito via **sessão remota no Autosky** — uma plataforma de virtualização de desktop que entrega o SAP pelo navegador, sem necessidade de instalação local.

**Acesso:** Abra o navegador e acesse o portal Autosky com suas credenciais corporativas. Após login, inicie a sessão remota do SAP B1. VPN não é necessária — o Autosky já provê o acesso seguro. Usuário e senha SAP são **distintos** do usuário de rede; o TI realiza o cadastro inicial.

**Problemas comuns:**

- Não consigo conectar ao Autosky → Verifique sua conexão de internet; tente em outro navegador (Chrome ou Edge recomendados); limpe o cache (Ctrl+Shift+Del) e tente novamente
- Tela preta ao iniciar a sessão remota → Aguarde 30 segundos; se persistir, feche a aba, acesse o portal novamente e inicie uma nova sessão; acione o TI se o problema continuar
- Sessão travada / SAP não responde → Feche a aba do navegador, volte ao portal Autosky, encerre a sessão existente e abra uma nova; se a sessão aparecer como "em uso", acione o TI para forçar encerramento
- Erro de certificado ou "conexão não segura" no Autosky → Acione o TI — pode indicar problema de certificado no servidor ou proxy corporativo
- Esqueci minha senha SAP → Acione o TI para reset — a senha SAP é independente da senha de rede e de domínio
- Não tenho acesso ao Autosky → Solicite ao gestor que encaminhe pedido ao TI informando nome, cargo e perfil SAP necessário
- SAP abre mas aparece empresa/banco errado → Confirme com o TI qual empresa (base de dados) deve ser selecionada na tela de login do SAP

**Quem contatar se não resolver:** TI (sessão remota, Autosky, reset de senha SAP, criação de usuário)
""",
    ),
    Article(
        slug="sap-b1-duvidas-funcionais",
        title="SAP B1 — Dúvidas Funcionais",
        tags=["sap", "erp", "funcional", "estoque", "pedidos", "nfe"],
        body="""## SAP B1 — Dúvidas Funcionais

**O que é:** Artigo de referência para dúvidas de uso e operação do SAP Business One: consultas de estoque, lançamento de pedidos, notas fiscais, aprovações e demais funcionalidades do dia a dia.

**Acesso:** Ver artigo SAP B1 — Acesso (Autosky). Permissões de módulo (compras, estoque, financeiro, etc.) são configuradas pelo TI conforme perfil autorizado pelo gestor.

**Problemas comuns:**

- Não tenho permissão para acessar um módulo ou função → Solicite ao gestor que encaminhe ao TI a liberação do perfil adequado; descreva qual menu/função é necessária
- Pedido travado em aprovação → Verifique o status no fluxo de aprovação (aba Aprovação no documento); contate diretamente o aprovador responsável; o TI não intervém no fluxo de negócio
- Consulta de estoque exibe saldo incorreto → Verifique se o filtro de depósito e data está correto; o saldo reflete entradas/saídas já contabilizadas — entradas em trânsito podem não aparecer ainda
- Nota fiscal não foi gerada / status incorreto → Acione a equipe fiscal ou de faturamento; erros de SEFAZ ou rejeições de NF-e devem ser tratados pela equipe responsável
- Documento duplicado ou lançamento errado → **Nunca delete registros no SAP** — solicite à equipe responsável (Compras, Financeiro ou TI) o cancelamento nativo via SAP; a exclusão direta é procedimento proibido
- Relatório ou consulta não exibe dados esperados → Verifique filtros de data, filial e empresa; se suspeitar de erro no sistema, acione o TI com print e descrição detalhada
- Dúvida sobre como executar uma operação no SAP → Consulte o manual interno disponível na pasta de rede do TI; se não encontrar, acione o TI ou o responsável funcional da área

**Quem contatar se não resolver:** TI (erros técnicos, permissões, comportamento inesperado do sistema) / Equipe funcional responsável pela área (Compras, Financeiro, Logística, Fiscal) para dúvidas de processo
""",
    ),
    Article(
        slug="planejamento-financeiro-gestores",
        title="Planejamento Financeiro Gestores",
        tags=["planejamento", "financeiro", "gestores", "budget", "forecast"],
        body="""## Planejamento Financeiro Gestores

**O que é:** Plataforma ou planilha centralizada utilizada pelos gestores para elaboração, acompanhamento e revisão do planejamento financeiro (forecast, budget e revisões periódicas) de suas áreas.

**Acesso:** Acesso via intranet ou compartilhamento de rede. Gestores recebem acesso após solicitação formal à Controladoria. Pode requerer VPN fora da rede.

**Problemas comuns:**

- Não tenho acesso ao planejamento → Solicite à Controladoria — o acesso é liberado mediante autorização do diretor da área
- Não consigo editar os campos → Verifique se o período de planejamento está aberto; fora da janela definida pela Controladoria, o arquivo fica bloqueado para edição
- Arquivo não abre / erro de compatibilidade → Confirme que está usando a versão correta do Office (mínimo recomendado: Microsoft 365); acione o TI se o problema persistir
- Dados desatualizados → O arquivo é atualizado pela Controladoria conforme calendário; verifique a data da última atualização indicada na aba de controle
- Não consigo salvar minhas alterações → Verifique permissões de escrita na pasta de rede; tente salvar localmente e depois reenviar para a Controladoria

**Quem contatar se não resolver:** Controladoria (acessos, permissões e dúvidas sobre dados) / TI (erros técnicos de arquivo ou rede)
""",
    ),
    Article(
        slug="treinamento-desenvolvimento",
        title="T&D — Treinamento & Desenvolvimento",
        tags=["treinamento", "desenvolvimento", "rh", "lms", "cursos"],
        body="""## T&D — Treinamento & Desenvolvimento

**O que é:** Plataforma de gestão de treinamentos corporativos (LMS — Learning Management System) onde colaboradores acessam cursos obrigatórios, trilhas de aprendizagem e certificações internas.

**Acesso:** Acesso via navegador. Login com e-mail corporativo ou usuário de rede. Link e credenciais iniciais enviados pelo RH no onboarding.

**Problemas comuns:**

- Não recebi acesso à plataforma → Acione o RH para criação do usuário; novos colaboradores devem receber o acesso nas primeiras 48h
- Esqueci minha senha → Use a opção "Esqueci minha senha" na tela de login; o e-mail de recuperação vai para o e-mail corporativo
- Curso não aparece para mim → Alguns cursos são atribuídos pelo RH ou gestor — confirme se a trilha já foi vinculada ao seu perfil
- Vídeo não reproduz / áudio sem som → Verifique se o navegador está atualizado e se o Flash/HTML5 está habilitado; teste em outro navegador; confirme volume do sistema
- Certificado não foi gerado após conclusão → Certifique-se de ter concluído 100% do conteúdo e a avaliação (se houver); aguarde até 1 hora para geração automática; acione o RH se não aparecer
- Progresso não salvo → Não feche o navegador durante o treinamento; use o botão de pausa/salvar da plataforma quando for interromper

**Quem contatar se não resolver:** RH (atribuição de cursos, criação de usuário, certificados) / TI (falhas técnicas de acesso ou reprodução)
""",
    ),
    Article(
        slug="programa-5s",
        title="5S — Qualidade e Organização",
        tags=["5s", "qualidade", "auditoria", "organizacao"],
        body="""## 5S — Qualidade e Organização

**O que é:** Sistema de registro e acompanhamento do programa 5S (Seiri, Seiton, Seiso, Seiketsu, Shitsuke) — organização e padronização de ambientes de trabalho. Permite agendamento de auditorias, registro de evidências e acompanhamento de planos de ação.

**Acesso:** Acesso via intranet corporativa com usuário e senha corporativos. Perfis são definidos por área (auditor, auditado, gestor).

**Problemas comuns:**

- Não consigo acessar o sistema → Use as credenciais corporativas; se for primeiro acesso, solicite ao responsável do programa 5S ou ao TI
- Não consigo registrar evidências (fotos) → Verifique o tamanho máximo do arquivo (geralmente até 5 MB por imagem); use JPEG; verifique se o armazenamento do servidor está disponível
- Auditoria não aparece no meu calendário → Confirme com o auditor responsável se você foi incluído na lista de auditados; acesse o módulo de agenda
- Plano de ação não atualiza → Verifique se você tem perfil de responsável pela ação; ações só podem ser editadas pelo responsável designado
- Relatório de auditoria não gera → Tente em outro navegador; limpe o cache; acione o TI se persistir

**Quem contatar se não resolver:** Responsável local do programa 5S (dúvidas de processo) / TI (falhas técnicas)
""",
    ),
    Article(
        slug="mpv",
        title="MPV — Melhoria de Processos",
        tags=["mpv", "melhoria", "processos", "indicadores"],
        body="""## MPV

**O que é:** Sistema de controle e gestão do MPV (Melhoria de Processos e Vendas ou módulo equivalente interno), utilizado para registro de oportunidades de melhoria, acompanhamento de indicadores e gestão de ações corretivas.

**Acesso:** Acesso via intranet com credenciais corporativas. Perfis de acesso por área são configurados pelo TI mediante solicitação do gestor.

**Problemas comuns:**

- Não tenho acesso ao sistema → Solicite ao gestor que encaminhe pedido ao TI informando seu nome, área e perfil necessário
- Não consigo criar novos registros → Verifique se seu perfil tem permissão de criação; perfis de "visualização" não permitem edição
- Registro travado sem possibilidade de edição → Registros fechados/aprovados ficam somente leitura; contate o responsável para reabertura se necessário
- Notificações não chegam por e-mail → Confirme se o e-mail cadastrado no sistema está correto; verifique pasta de spam; acione o TI para revisar as configurações de alerta
- Tela em branco ao abrir → Limpe o cache do navegador (Ctrl+Shift+Del); tente em modo anônimo ou outro navegador

**Quem contatar se não resolver:** TI (acesso, permissões, falhas técnicas) / Gestor da área (aprovações e fluxo de processos)
""",
    ),
    Article(
        slug="drop",
        title="DROP — Demandas e Registros Operacionais",
        tags=["drop", "demandas", "operacoes", "fluxo"],
        body="""## DROP

**O que é:** Plataforma ou módulo de gestão de DROP (Demandas, Registros e Operações de Processo), utilizado para controle de demandas operacionais, ocorrências e fluxos de trabalho entre equipes.

**Acesso:** Acesso via intranet com credenciais corporativas. Usuários são cadastrados pelo TI mediante solicitação do gestor responsável.

**Problemas comuns:**

- Não consigo fazer login → Confirme que está usando o usuário de rede sem domínio (@empresa); redefina a senha pelo portal corporativo se necessário
- Não vejo as demandas da minha equipe → Verifique se o filtro de área/equipe está correto; pode ser necessário que o gestor ajuste seu perfil para incluir visualização da equipe
- Não consigo alterar status de uma demanda → Apenas o responsável designado ou o gestor podem alterar certos status; verifique o fluxo de aprovação
- Sistema lento ou travando → Limpe o cache; verifique sua conexão de rede; acione o TI se a lentidão for generalizada
- Não recebi notificação de nova demanda → Verifique spam; confirme com o TI se as notificações estão ativas no seu perfil

**Quem contatar se não resolver:** TI (acesso, criação de usuário, falhas técnicas) / Gestor (fluxos e permissões de equipe)
""",
    ),
    Article(
        slug="data-masking",
        title="Data Masking — Anonimização de Dados",
        tags=["data-masking", "lgpd", "privacidade", "ti", "dados"],
        body="""## Data Masking

**O que é:** Ferramenta de mascaramento de dados sensíveis utilizada pelo TI para anonimizar informações de produção antes de disponibilizá-las em ambientes de desenvolvimento e homologação, em conformidade com a LGPD.

**Acesso:** Acesso restrito à equipe de TI. Desenvolvedores e analistas que precisam de dados para testes devem solicitar ao TI um dump mascarado — **nunca utilizar dados reais de produção em dev/homologação sem mascaramento**.

**Problemas comuns:**

- Preciso de dados para testes → Abra chamado no TI solicitando extração mascarada; informe sistema de origem, volume aproximado e finalidade
- Os dados mascarados estão com formato incorreto (CPF, CNPJ, e-mail) → Reporte ao TI especificando o campo e o formato esperado para ajuste nas regras de mascaramento
- Processo de mascaramento demorou mais que o esperado → Extrações grandes podem levar horas; confirme com o TI o prazo estimado no chamado
- Dúvida sobre quais dados precisam ser mascarados → Consulte o TI ou o DPO (LGPD); dados pessoais, financeiros e de saúde são sempre mascarados

**Quem contatar se não resolver:** TI — equipe de banco de dados / DPO (dúvidas sobre classificação de dados)
""",
    ),
    Article(
        slug="gpt-corporativo",
        title="GPT Corporativo — Assistente de IA",
        tags=["gpt", "ia", "produtividade", "llm"],
        body="""## GPT Corporativo

**O que é:** Assistente de IA generativa corporativo, baseado em modelo de linguagem (LLM), disponibilizado internamente para apoio a redigir textos, resumir documentos, tirar dúvidas e aumentar produtividade — com controles de privacidade de dados.

**Acesso:** Acesso via navegador pela intranet. Login com credenciais corporativas. Disponível apenas para colaboradores autorizados — o acesso é liberado pelo TI mediante solicitação.

**Problemas comuns:**

- Não tenho acesso à ferramenta → Solicite ao TI informando nome, cargo e justificativa de uso; acesso é liberado conforme política interna
- Minhas respostas foram cortadas / incompletas → O assistente tem limite de tokens por resposta; divida perguntas longas em partes menores ou peça continuação explicitamente
- O sistema retornou uma resposta incorreta ou inadequada → Não use a resposta sem validação; reformule a pergunta; reporte ao TI se o comportamento for recorrente ou inadequado
- Não consigo fazer upload de documentos → Verifique o tamanho máximo permitido (consulte o TI); formatos aceitos geralmente são PDF, DOCX e TXT
- Preocupação com privacidade de dados → **Não insira dados pessoais de clientes, colaboradores ou parceiros** na ferramenta; dúvidas sobre o que pode ser inserido, consulte o DPO
- Ferramenta lenta ou indisponível → Verifique sua conexão; o serviço pode estar em manutenção — aguarde e tente novamente em 15 min

**Quem contatar se não resolver:** TI (acesso e falhas técnicas) / DPO (dúvidas sobre uso adequado e privacidade)
""",
    ),
    Article(
        slug="pdf-tools",
        title="PDF Tools — Ferramentas de PDF",
        tags=["pdf", "ferramentas", "documentos", "conversao"],
        body="""## PDF Tools

**O que é:** Conjunto de ferramentas para manipulação de arquivos PDF disponibilizado internamente: conversão, compressão, fusão, divisão e assinatura de documentos PDF, sem necessidade de enviar arquivos para serviços externos.

**Acesso:** Acesso via intranet ou aplicativo instalado na estação. Não requer VPN para uso na rede interna. Para instalação em novo computador, acione o TI.

**Problemas comuns:**

- A ferramenta não está instalada no meu computador → Abra chamado no TI solicitando instalação; informe o nome do equipamento (hostname)
- Não consigo converter PDF para Word / Excel → Confirme que o arquivo PDF não é protegido contra edição; PDFs gerados de escaneamento (imagem) requerem OCR — verifique se a função OCR está disponível
- Arquivo PDF gerado está muito grande → Use a função de compressão; imagens dentro do PDF aumentam muito o tamanho
- Assinatura digital não é reconhecida → Confirme que o certificado digital está instalado e válido; acione o TI para verificar o certificado
- Erro ao mesclar vários PDFs → Verifique se algum dos arquivos está protegido por senha; arquivos corrompidos também causam falha na mesclagem

**Quem contatar se não resolver:** TI (instalação, configuração de certificado, falhas técnicas)
""",
    ),
    Article(
        slug="boardadvisor",
        title="BoardAdvisor — Governança Corporativa",
        tags=["boardadvisor", "governanca", "diretoria", "conselho", "atas"],
        body="""## BoardAdvisor

**O que é:** Plataforma de governança corporativa e gestão de reuniões de diretoria/conselho, utilizada para distribuição de pautas, atas, votações e documentos confidenciais entre membros do conselho e alta liderança.

**Acesso:** Acesso via navegador ou aplicativo móvel. Login com e-mail corporativo. Acesso restrito a usuários explicitamente convidados — a inclusão é feita pelo administrador da plataforma (geralmente Relações Institucionais ou Diretoria).

**Problemas comuns:**

- Não recebi o convite de acesso → Verifique spam; confirme com o responsável pela reunião se seu e-mail foi cadastrado corretamente na plataforma
- Não consigo fazer login → Use o e-mail corporativo; se for primeiro acesso, use o link de ativação do convite (tem validade de 48h — solicite reenvio se expirado)
- Não vejo os documentos da reunião → Documentos são publicados pelo administrador; confirme com o organizador da reunião se a publicação foi feita
- Aplicativo móvel não sincroniza → Verifique conexão com internet; force o fechamento e reabertura do app; se persistir, desinstale e reinstale
- Preciso acessar ata de reunião anterior → Verifique o arquivo histórico na plataforma; se não encontrar, solicite ao responsável pelo BoardAdvisor

**Quem contatar se não resolver:** Relações Institucionais ou responsável pelo BoardAdvisor (permissões e acesso) / TI (falhas técnicas)
""",
    ),
    Article(
        slug="gerenciamento-projetos",
        title="Gerenciamento de Projetos",
        tags=["projetos", "gestao", "pm", "cronograma", "tarefas"],
        body="""## Gerenciamento de Projetos

**O que é:** Plataforma corporativa de gestão de projetos utilizada para planejamento, acompanhamento de tarefas, controle de cronograma e colaboração entre equipes em projetos internos.

**Acesso:** Acesso via navegador pela intranet com credenciais corporativas. Novos usuários são cadastrados pelo TI mediante solicitação do gestor do projeto.

**Problemas comuns:**

- Não tenho acesso a um projeto específico → Solicite ao gerente do projeto que te adicione como membro; o acesso por projeto é controlado pelo PM (project manager)
- Não consigo criar novos projetos → Perfis de criação de projeto são restritos; solicite ao TI a elevação de permissão com aprovação do gestor
- Notificações de tarefas não chegam → Verifique as configurações de notificação dentro da plataforma (perfil → notificações); confirme que o e-mail está correto; verifique spam
- Cronograma não atualiza após alterar datas → Verifique se há dependências entre tarefas que bloqueiam o ajuste; consulte o PM do projeto
- Não consigo anexar arquivos → Verifique o tamanho máximo permitido (geralmente 25 MB); para arquivos maiores, use o servidor de arquivos de rede e cole o link no comentário
- Tela em branco ou carregamento infinito → Limpe o cache do navegador; desative extensões; tente em modo anônimo; acione o TI se persistir
- Projeto arquivado sumiu → Projetos concluídos são arquivados automaticamente — verifique o filtro "Arquivados" ou "Concluídos" na listagem

**Quem contatar se não resolver:** TI (acesso, permissões, falhas técnicas) / Gerente do projeto (inclusão em projetos, fluxos e permissões internas)
""",
    ),
    Article(
        slug="anotado",
        title="Anotado — Ferramenta de Anotações",
        tags=["anotado", "notas", "produtividade", "conhecimento"],
        body="""## Anotado

**O que é:** Ferramenta corporativa de anotações e gestão de conhecimento pessoal, utilizada para criar, organizar e compartilhar notas, checklists e documentos rápidos no dia a dia de trabalho.

**Acesso:** Acesso via navegador ou aplicativo instalado. Login com credenciais corporativas. Para instalação em novo equipamento, acione o TI.

**Problemas comuns:**

- Não consigo fazer login → Confirme que está usando o e-mail corporativo; tente redefinir a senha pelo fluxo "Esqueci minha senha"; acione o TI se o problema persistir
- Minhas anotações não aparecem em outro dispositivo → Verifique se está logado com o mesmo usuário; a sincronização pode levar alguns minutos — aguarde e atualize a página
- Perdi uma anotação / deletei sem querer → Verifique a lixeira dentro da ferramenta; muitas plataformas mantêm itens excluídos por até 30 dias antes da exclusão permanente
- Não consigo compartilhar uma nota com colega → Confirme que o colega também tem acesso à ferramenta; verifique as permissões de compartilhamento (visualização vs. edição)
- Formatação quebrada ao colar texto externo → Cole usando Ctrl+Shift+V (colar sem formatação) e aplique o estilo desejado diretamente na ferramenta
- Aplicativo não sincroniza / fica offline → Verifique conexão de internet; feche e reabra o aplicativo; se persistir, desinstale e reinstale

**Quem contatar se não resolver:** TI (acesso, instalação, falhas técnicas de sincronização)
""",
    ),
    Article(
        slug="vpn-acesso-remoto-mfa",
        title="VPN — Acesso Remoto com MFA (OpenVPN + Google Authenticator)",
        tags=["vpn", "mfa", "acesso-remoto", "seguranca", "openvpn"],
        body="""## VPN — Acesso Remoto com MFA (OpenVPN + Google Authenticator)

**O que é:** A VPN corporativa (OpenVPN) permite acesso seguro aos sistemas internos fora da rede da empresa. A autenticação usa MFA (fator duplo): PIN fixo + código temporário do Google Authenticator.

**Acesso:** Requer o cliente OpenVPN instalado no computador e o app Google Authenticator configurado no celular. Para instalação do OpenVPN ou obtenção do QR Code, abra chamado no helpdesk.

### Pré-requisito: instalar o Google Authenticator
- **Android:** Google Play → pesquise "Google Authenticator"
- **iOS:** App Store → pesquise "Google Authenticator"

### Configuração inicial (fazer uma única vez)
1. Abra o Google Authenticator no celular
2. Toque em **"+"** → **"Escanear QR Code"**
3. Escaneie o QR Code enviado pelo TI por e-mail
4. O app passa a exibir um código de 6 dígitos que se renova a cada 30 segundos

### Como conectar à VPN
1. Abra o **OpenVPN** no computador
2. **Usuário:** seu login corporativo (recebido no email, geralmente nome e sobrenome juntos)
3. **Senha:** PIN fixo + código atual do Google Authenticator, sem espaço
   > PIN padrão: `2304` — Exemplo: PIN `2304` + código `567890` → digite `2304567890`

**Problemas comuns:**

- "Credenciais inválidas" ao tentar conectar → O código de 6 dígitos expirou (validade: 30s); aguarde o próximo código aparecer no app e tente novamente imediatamente
- Não recebi o QR Code por e-mail → Verifique spam; se não encontrar, abra chamado no helpdesk para reenvio
- Esqueci meu PIN fixo → Abra chamado no helpdesk; o PIN não pode ser recuperado pelo usuário — o TI gerará um novo
- OpenVPN não está instalado no computador → Abra chamado no helpdesk solicitando instalação; informe o hostname do equipamento
- Celular trocado / perdi o acesso ao Google Authenticator → Abra chamado no helpdesk para recadastrar o MFA com novo QR Code; não é possível transferir códigos entre dispositivos sem esse processo
- VPN conecta mas não acessa os sistemas internos → Verifique se a conexão VPN está ativa (ícone na barra de tarefas); tente reconectar; acione o TI se persistir

**Quem contatar se não resolver:** TI (instalação do OpenVPN, QR Code, reset de PIN, problemas de conexão)
""",
    ),
]

# ---------------------------------------------------------------------------
# Main ingestion loop
# ---------------------------------------------------------------------------

SEED_USER_ID = "00000000-0000-0000-0000-000000000001"  # system/seed actor


async def main() -> None:
    import os
    sys.path.insert(0, "/app")

    # Must import after sys.path is set
    from sqlalchemy import text as sa_text
    from app.db.session import get_db
    from app.services.rag import ingester

    # Create a standalone session (not via FastAPI dependency injection)
    from app.db.session import _Session  # noqa: PLC2701

    ok = 0
    failed = 0

    async with _Session() as db:
        for art in ARTICLES:
            try:
                # Insert article (skip if slug already exists)
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
                    print(f"  [SKIP] {art.slug} — already exists")
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

    print(f"\nDone: {ok} OK, {failed} failed out of {len(ARTICLES)} articles.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
