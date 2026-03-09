---
name: contact-rate-analysis
description: >
  Analisa dados de contatos com o time de atendimento (CS/Suporte) de uma corretora distribuidora
  de fundos de investimento para identificar oportunidades de redução de Contact Rate. Recebe
  CSV ou Excel com registros de atendimento e produz relatório analítico com recomendações
  priorizadas por impacto. Use esta skill sempre que o usuário mencionar: análise de contatos,
  contact rate, redução de chamados, atendimento ao cliente em corretora/DTVM, motivos de
  contato, ticket analysis, análise de suporte, categorização de chamados, ou qualquer pedido
  envolvendo dados de atendimento ao investidor em contexto de distribuição de fundos.
  Também acione quando o usuário pedir para analisar planilhas de chamados, exportações de
  Zendesk/Intercom/Freshdesk, ou dados de CRM relacionados a atendimento de investidores.
---

# Contact Rate Analysis — Corretora Distribuidora de Fundos

Skill para análise de contatos com atendimento ao cliente no contexto de uma corretora
distribuidora de fundos de investimento. O objetivo central é transformar dados brutos de
atendimento em insights acionáveis para reduzir o Contact Rate, categorizando contatos,
identificando padrões evitáveis e propondo ações concretas com estimativa de impacto.

## Contexto de Negócio

A distribuição de fundos de investimento possui particularidades que geram categorias
específicas de contato. Entender o domínio é essencial para uma boa categorização.

**Jornadas típicas do investidor que geram contato:**

- Onboarding: cadastro, suitability, envio de documentos, abertura de conta
- Operacional: aplicação, resgate, portabilidade entre fundos, movimentação entre contas
- Informacional: rentabilidade, extrato, posição consolidada, comparação entre fundos
- Tributário: come-cotas (Lei 14.754/2023), IR sobre rendimentos, DARF, informe de rendimentos
- Técnico: acesso à plataforma, erros em transações, lentidão, problemas no app
- Regulatório: atualização cadastral periódica, adequação a novas normas CVM
- Pós-venda: dúvidas sobre fundo adquirido, insatisfação com rentabilidade, pedido de recomendação

## Workflow

### 1. Receber e validar os dados

O usuário vai fornecer um arquivo CSV ou Excel (.xlsx/.xls) com registros de atendimento.

**Ação:** Leia o arquivo usando Python (pandas). Identifique as colunas disponíveis e mapeie-as
para o schema esperado. Não exija colunas específicas — adapte-se ao que vier.

Colunas comuns que você pode encontrar (nomes podem variar):
- Identificador do chamado/ticket
- Data/hora de abertura (e opcionalmente fechamento)
- Canal de contato (chat, telefone, e-mail, WhatsApp)
- Motivo ou categoria do contato (pode ou não existir)
- Descrição/resumo do contato (texto livre)
- Status (aberto, resolvido, pendente)
- Tempo de resolução
- Agente/atendente
- Informações do cliente (segmento, patrimônio, tempo de casa)

**Mapeamento flexível:** Use heurísticas para identificar colunas mesmo que os nomes não sejam
exatos. Por exemplo, colunas contendo "motivo", "razão", "categoria", "tipo" provavelmente
indicam a categorização do contato. Colunas com "desc", "resumo", "detalhe", "observação"
provavelmente contêm texto livre.

Se o arquivo não tiver uma coluna de categorização, use o texto livre (descrição/resumo) para
classificar os contatos automaticamente usando as categorias do domínio listadas acima.

Apresente ao usuário um resumo do que foi encontrado:
- Total de registros
- Período coberto
- Colunas identificadas e seu mapeamento
- Qualidade dos dados (campos vazios, duplicatas, etc.)

### 2. Categorizar os contatos

Classifique cada contato em uma taxonomia de dois níveis:

**Nível 1 — Macro-categoria:**
- `ONBOARDING` — Cadastro, abertura de conta, suitability, documentação
- `OPERACIONAL` — Aplicação, resgate, portabilidade, movimentação
- `INFORMACIONAL` — Rentabilidade, extrato, posição, comparações
- `TRIBUTARIO` — Come-cotas, IR, DARF, informe de rendimentos
- `TECNICO` — Plataforma, app, erros, acesso
- `REGULATORIO` — Atualização cadastral, compliance, adequação normativa
- `POS_VENDA` — Insatisfação, reclamação, dúvida pós-compra
- `OUTRO` — Contatos que não se encaixam nas categorias acima

**Nível 2 — Motivo específico:** Dentro de cada macro-categoria, identifique os motivos
específicos mais frequentes. Não force uma lista pré-definida — deixe os dados revelarem
os motivos reais. O objetivo é ter granularidade suficiente para ação.

**Como categorizar:**

Se já houver uma coluna de categoria no arquivo, use-a como base, mas valide e reagrupe
conforme a taxonomia acima. Categorias genéricas como "Dúvida" ou "Outros" devem ser
reclassificadas usando o texto livre quando disponível.

Se não houver categoria, analise o texto livre de cada registro. Use processamento de
linguagem natural para extrair o motivo do contato. Busque palavras-chave e padrões do domínio:
- "resgate", "resgatar" → OPERACIONAL / Resgate
- "rentabilidade", "rendimento", "quanto rendeu" → INFORMACIONAL / Rentabilidade
- "come-cotas", "imposto", "IR" → TRIBUTARIO
- "não consigo acessar", "erro", "tela travou" → TECNICO / Acesso ou Erro
- "suitability", "perfil de investidor" → ONBOARDING / Suitability

### 3. Analisar padrões e oportunidades

Com os contatos categorizados, produza as seguintes análises:

**3.1 Distribuição por categoria**
Calcule volume e percentual de cada macro-categoria e motivo específico. Identifique os
top 10 motivos por volume — esses são os alvos prioritários de redução.

**3.2 Classificação de evitabilidade**
Para cada motivo frequente, classifique em:
- `EVITÁVEL_SELF_SERVICE` — O investidor poderia resolver sozinho com melhor UX, FAQ, ou chatbot
- `EVITÁVEL_PROATIVO` — A corretora poderia antecipar com comunicação proativa (push, e-mail)
- `EVITÁVEL_AUTOMAÇÃO` — O processo pode ser automatizado end-to-end
- `EVITÁVEL_UX` — O contato acontece por fricção na interface/jornada
- `REDUTÍVEL` — Não é eliminável, mas pode ter volume reduzido com melhorias
- `NECESSÁRIO` — Contato legítimo que agrega valor (consultoria, casos complexos)

**3.3 Análise temporal**
Se houver dados de data, identifique:
- Tendências ao longo do tempo (crescimento/redução de categorias)
- Sazonalidade (picos em datas de come-cotas, declaração de IR, janelas de resgate)
- Correlação com eventos de mercado (volatilidade, queda da bolsa → mais contatos informacionais)

**3.4 Análise por canal**
Se houver dados de canal, compare a distribuição de motivos entre canais. Isso revela
oportunidades de deflexão (ex: contatos por telefone que poderiam ser resolvidos via chat/FAQ).

**3.5 Métricas de eficiência**
Se houver tempo de resolução, calcule:
- Tempo médio por categoria
- Categorias com maior custo operacional (volume × tempo)
- Essa métrica ajuda a priorizar — resolver 100 tickets que levam 20 min cada é mais
  impactante que resolver 100 tickets de 2 min cada.

### 4. Gerar recomendações priorizadas

Para cada oportunidade identificada, produza uma recomendação estruturada:

```
RECOMENDAÇÃO: [Título conciso]
CATEGORIA ALVO: [Macro > Motivo específico]
VOLUME IMPACTADO: [N contatos/mês — X% do total]
CLASSIFICAÇÃO: [EVITÁVEL_SELF_SERVICE | EVITÁVEL_PROATIVO | etc.]
ESFORÇO ESTIMADO: [Baixo | Médio | Alto]
IMPACTO ESTIMADO: [Redução de X-Y% dos contatos dessa categoria]
AÇÃO PROPOSTA: [Descrição concreta da ação]
QUICK WIN: [Sim/Não — pode ser implementado em < 2 semanas?]
```

**Priorização:** Ordene as recomendações usando um score composto:
- Score = (Volume Impactado × % Redução Esperada) / Esforço
- Onde Esforço: Baixo=1, Médio=2, Alto=3
- Quick wins com score alto vêm primeiro

**Exemplos de recomendações típicas no domínio de fundos:**

- "Implementar FAQ dinâmico sobre come-cotas" → Para contatos TRIBUTARIO/come-cotas que
  aumentam em maio e novembro
- "Notificação push pós-resgate com prazo de liquidação" → Para contatos OPERACIONAL
  perguntando "cadê meu dinheiro" após solicitar resgate (D+1, D+30, etc.)
- "Status tracker de portabilidade na área logada" → Para contatos OPERACIONAL
  perguntando sobre andamento de portabilidade
- "E-mail proativo pré-come-cotas explicando o impacto" → Comunicação que antecipa
  dúvidas recorrentes
- "Melhoria na tela de extrato com filtro por fundo" → Para contatos INFORMACIONAL
  onde o investidor não encontra informações na plataforma

### 5. Produzir o relatório

Gere um relatório analítico em Markdown contendo:

```
# Análise de Contact Rate — [Nome da Corretora ou "Corretora"]
## Período: [data início] a [data fim]

## Resumo Executivo
[3-5 parágrafos com os principais achados, volume total, categorias dominantes,
e o potencial estimado de redução]

## Visão Geral dos Dados
[Resumo do dataset: volume, período, canais, qualidade dos dados]

## Distribuição por Categoria
[Tabela com macro-categorias e motivos, volumes e percentuais]

## Análise de Evitabilidade
[Quanto do volume total é evitável? Breakdown por tipo de evitabilidade]

## Análise Temporal
[Tendências, sazonalidade, correlações — se houver dados de data]

## Análise por Canal
[Distribuição por canal, oportunidades de deflexão — se houver dados de canal]

## Recomendações Priorizadas
[Lista ordenada por score de prioridade, cada uma no formato estruturado acima]

## Estimativa de Impacto Consolidado
[Se todas as recomendações fossem implementadas, qual seria a redução esperada
no Contact Rate? Apresente cenários conservador, moderado e otimista.]

## Próximos Passos Sugeridos
[O que fazer com esse relatório: validar com CS, priorizar com produto, etc.]
```

Além do Markdown, se o usuário pedir, gere também uma versão .docx seguindo a skill de docx.

### 6. Gerar artefatos de suporte

Quando possível, gere também:

- **Tabela de dados categorizados** — CSV com os dados originais + colunas de categorização
  adicionadas, para que o time possa filtrar e explorar
- **Pareto chart data** — Dados prontos para visualizar os top motivos de contato
- **Matriz Impacto × Esforço** — Dados estruturados para plotar as recomendações

## Diretrizes importantes

**Seja específico ao domínio.** Recomendações genéricas como "melhorar a comunicação" não
ajudam. Prefira "Criar notificação automática D-3 antes do come-cotas de maio explicando que
o imposto será descontado automaticamente e que isso não significa perda de rentabilidade".

**Considere o nível de sofisticação do investidor.** Contatos sobre temas básicos (ex:
"o que é come-cotas?") indicam oportunidade de educação/onboarding. Contatos sobre temas
avançados (ex: "compensação de prejuízo entre fundos") indicam necessidade de consultoria
especializada — não devem ser deflectados.

**Reconheça limitações dos dados.** Se o dataset for pequeno, a categorização não tiver granularidade,
ou faltar informação temporal, deixe isso explícito. Não invente insights que os dados não suportam.

**Pense em product thinking.** A análise não é um fim em si — ela alimenta decisões de produto.
Conecte as recomendações a melhorias concretas na jornada do investidor (UX, fluxos, comunicação).

**Contexto regulatório.** Lembre que corretoras distribuidoras operam sob regulação CVM e ANBIMA.
Algumas interações de atendimento são obrigatórias (ex: atualização cadastral, adequação de
suitability). Essas não devem ser tratadas como "evitáveis" — mas podem ser otimizadas.
