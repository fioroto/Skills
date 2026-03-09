#!/usr/bin/env python3
"""
contact_analyzer.py — Processa e categoriza dados de atendimento de corretora distribuidora
de fundos de investimento para análise de Contact Rate.

Uso:
    python contact_analyzer.py <arquivo_input> [--output <dir_output>]

O script:
1. Lê CSV ou Excel
2. Mapeia colunas automaticamente
3. Categoriza contatos (2 níveis)
4. Calcula métricas e distribuições
5. Classifica evitabilidade
6. Gera recomendações priorizadas
7. Exporta resultados em JSON para o relatório
"""

import sys
import json
import os
from datetime import datetime
from collections import Counter, defaultdict
import re

try:
    import pandas as pd
except ImportError:
    print("Instalando pandas...")
    os.system("pip install pandas openpyxl --break-system-packages -q")
    import pandas as pd


# =============================================================================
# TAXONOMIA DE CATEGORIAS
# =============================================================================

MACRO_CATEGORIES = {
    "ONBOARDING": {
        "desc": "Cadastro, abertura de conta, suitability, documentação",
        "keywords": [
            "cadastro", "abertura", "conta", "suitability", "perfil de investidor",
            "documento", "documentação", "cpf", "comprovante", "selfie", "foto",
            "abrir conta", "criar conta", "dados cadastrais", "formulário",
            "termo de adesão", "contrato"
        ]
    },
    "OPERACIONAL": {
        "desc": "Aplicação, resgate, portabilidade, movimentação",
        "keywords": [
            "aplicação", "aplicar", "resgate", "resgatar", "portabilidade",
            "transferência", "movimentação", "liquidação", "d+", "prazo",
            "cotização", "cota", "aporte", "investir", "movimentar",
            "ted", "pix", "depósito", "saldo", "cadê meu dinheiro",
            "não caiu", "demora", "prazo de resgate"
        ]
    },
    "INFORMACIONAL": {
        "desc": "Rentabilidade, extrato, posição, comparações",
        "keywords": [
            "rentabilidade", "rendimento", "quanto rendeu", "extrato",
            "posição", "saldo", "consolidado", "performance", "benchmark",
            "cdi", "comparação", "comparar", "histórico", "evolução",
            "quanto tenho", "meu patrimônio", "carteira"
        ]
    },
    "TRIBUTARIO": {
        "desc": "Come-cotas, IR, DARF, informe de rendimentos",
        "keywords": [
            "come-cotas", "come cotas", "imposto", "ir", "darf",
            "informe de rendimentos", "declaração", "tributação", "tributo",
            "iof", "alíquota", "tabela regressiva", "compensação",
            "prejuízo", "imposto de renda", "receita federal",
            "lei 14754", "lei 14.754"
        ]
    },
    "TECNICO": {
        "desc": "Plataforma, app, erros, acesso",
        "keywords": [
            "erro", "bug", "não consigo", "não funciona", "travou",
            "lento", "lentidão", "app", "aplicativo", "plataforma",
            "login", "senha", "acesso", "tela", "carregando",
            "não abre", "problema técnico", "sistema fora"
        ]
    },
    "REGULATORIO": {
        "desc": "Atualização cadastral, compliance, adequação normativa",
        "keywords": [
            "atualização cadastral", "recadastro", "cvm", "anbima",
            "compliance", "pld", "lavagem", "adequação", "normativa",
            "regulação", "bloqueio", "bloqueado", "pendência cadastral"
        ]
    },
    "POS_VENDA": {
        "desc": "Insatisfação, reclamação, dúvida pós-compra, recomendação",
        "keywords": [
            "insatisf", "reclamação", "reclamar", "perdi dinheiro",
            "caiu", "desvalorizou", "não recomend", "arrependimento",
            "trocar de fundo", "sugestão", "recomendação", "assessor",
            "consultor", "qual fundo", "melhor fundo"
        ]
    }
}

# Heurísticas de evitabilidade por motivo
EVITABILITY_RULES = {
    "ONBOARDING": {
        "default": "REDUTÍVEL",
        "overrides": {
            "documento": "EVITÁVEL_UX",
            "suitability": "NECESSÁRIO",
            "formulário": "EVITÁVEL_UX",
        }
    },
    "OPERACIONAL": {
        "default": "EVITÁVEL_PROATIVO",
        "overrides": {
            "prazo": "EVITÁVEL_PROATIVO",
            "status": "EVITÁVEL_SELF_SERVICE",
            "portabilidade": "EVITÁVEL_SELF_SERVICE",
            "erro": "EVITÁVEL_AUTOMAÇÃO",
        }
    },
    "INFORMACIONAL": {
        "default": "EVITÁVEL_SELF_SERVICE",
        "overrides": {
            "rentabilidade": "EVITÁVEL_SELF_SERVICE",
            "extrato": "EVITÁVEL_UX",
            "comparação": "EVITÁVEL_SELF_SERVICE",
        }
    },
    "TRIBUTARIO": {
        "default": "EVITÁVEL_PROATIVO",
        "overrides": {
            "come-cotas": "EVITÁVEL_PROATIVO",
            "informe": "EVITÁVEL_SELF_SERVICE",
            "compensação": "NECESSÁRIO",
        }
    },
    "TECNICO": {
        "default": "EVITÁVEL_AUTOMAÇÃO",
        "overrides": {
            "acesso": "EVITÁVEL_SELF_SERVICE",
            "senha": "EVITÁVEL_SELF_SERVICE",
        }
    },
    "REGULATORIO": {
        "default": "NECESSÁRIO",
        "overrides": {
            "atualização cadastral": "REDUTÍVEL",
        }
    },
    "POS_VENDA": {
        "default": "NECESSÁRIO",
        "overrides": {
            "recomendação": "NECESSÁRIO",
            "insatisf": "REDUTÍVEL",
        }
    }
}


# =============================================================================
# MAPEAMENTO DE COLUNAS
# =============================================================================

COLUMN_MAPPING_HEURISTICS = {
    "id": ["id", "ticket", "chamado", "protocolo", "numero", "número", "nº", "code", "código"],
    "data": ["data", "date", "criado", "abertura", "created", "timestamp", "dt_abertura", "data_abertura"],
    "data_fim": ["fechamento", "encerramento", "resolved", "closed", "dt_fechamento", "data_fechamento"],
    "canal": ["canal", "channel", "origem", "source", "meio", "tipo_canal"],
    "categoria": ["categoria", "category", "motivo", "reason", "tipo", "type", "assunto", "subject", "classificação"],
    "descricao": ["descricao", "descrição", "description", "resumo", "summary", "detalhe", "observação",
                   "obs", "mensagem", "message", "texto", "text", "conteudo", "conteúdo", "relato"],
    "status": ["status", "situação", "situacao", "state", "estado"],
    "tempo_resolucao": ["tempo", "duration", "tempo_resolução", "sla", "tempo_resolucao", "minutos", "horas"],
    "agente": ["agente", "agent", "atendente", "operador", "analista", "responsável"],
    "segmento": ["segmento", "segment", "perfil", "tier", "faixa", "categoria_cliente"],
    "patrimonio": ["patrimonio", "patrimônio", "aum", "saldo", "valor", "volume"]
}


def map_columns(df):
    """Mapeia colunas do DataFrame para o schema esperado usando heurísticas."""
    mapping = {}
    df_cols_lower = {col: col.lower().strip() for col in df.columns}

    for target, keywords in COLUMN_MAPPING_HEURISTICS.items():
        for col, col_lower in df_cols_lower.items():
            if col_lower in keywords or any(kw in col_lower for kw in keywords):
                if target not in mapping:
                    mapping[target] = col
                break

    return mapping


# =============================================================================
# CATEGORIZAÇÃO
# =============================================================================

def categorize_text(text):
    """Categoriza um texto livre em macro-categoria e motivo específico."""
    if not isinstance(text, str) or not text.strip():
        return "OUTRO", "Não identificado"

    text_lower = text.lower().strip()
    scores = {}

    for macro, info in MACRO_CATEGORIES.items():
        score = 0
        matched_keyword = None
        for kw in info["keywords"]:
            if kw in text_lower:
                score += len(kw)  # Palavras-chave mais longas = mais específicas
                if matched_keyword is None or len(kw) > len(matched_keyword):
                    matched_keyword = kw
        if score > 0:
            scores[macro] = (score, matched_keyword)

    if not scores:
        return "OUTRO", "Não categorizado"

    best_macro = max(scores, key=lambda k: scores[k][0])
    best_keyword = scores[best_macro][1]

    return best_macro, best_keyword.title()


def categorize_existing(category_text):
    """Tenta mapear uma categoria existente para a taxonomia padrão."""
    if not isinstance(category_text, str) or not category_text.strip():
        return "OUTRO", "Não identificado"

    text_lower = category_text.lower().strip()

    for macro, info in MACRO_CATEGORIES.items():
        for kw in info["keywords"]:
            if kw in text_lower:
                return macro, category_text.strip()

    return "OUTRO", category_text.strip()


def classify_evitability(macro, motivo_lower):
    """Classifica a evitabilidade de um motivo de contato."""
    rules = EVITABILITY_RULES.get(macro, {"default": "REDUTÍVEL", "overrides": {}})

    for keyword, classification in rules["overrides"].items():
        if keyword in motivo_lower:
            return classification

    return rules["default"]


# =============================================================================
# ANÁLISE
# =============================================================================

def analyze_data(df, col_map):
    """Executa todas as análises sobre os dados categorizados."""
    results = {
        "resumo": {},
        "distribuicao": {},
        "evitabilidade": {},
        "temporal": None,
        "canal": None,
        "eficiencia": None,
        "recomendacoes": []
    }

    total = len(df)
    results["resumo"]["total_contatos"] = total

    # Período
    if "data" in col_map and col_map["data"] in df.columns:
        try:
            dates = pd.to_datetime(df[col_map["data"]], errors="coerce", dayfirst=True)
            results["resumo"]["periodo_inicio"] = str(dates.min().date()) if pd.notna(dates.min()) else None
            results["resumo"]["periodo_fim"] = str(dates.max().date()) if pd.notna(dates.max()) else None
            df["_data_parsed"] = dates
        except Exception:
            pass

    # --- Distribuição por categoria ---
    macro_counts = df["_macro_categoria"].value_counts().to_dict()
    motivo_counts = df.groupby(["_macro_categoria", "_motivo"]).size().reset_index(name="count")
    motivo_counts = motivo_counts.sort_values("count", ascending=False)

    results["distribuicao"]["macro"] = {
        k: {"count": int(v), "pct": round(v / total * 100, 1)}
        for k, v in macro_counts.items()
    }

    results["distribuicao"]["motivos_top20"] = []
    for _, row in motivo_counts.head(20).iterrows():
        results["distribuicao"]["motivos_top20"].append({
            "macro": row["_macro_categoria"],
            "motivo": row["_motivo"],
            "count": int(row["count"]),
            "pct": round(row["count"] / total * 100, 1)
        })

    # --- Evitabilidade ---
    evit_counts = df["_evitabilidade"].value_counts().to_dict()
    results["evitabilidade"] = {
        k: {"count": int(v), "pct": round(v / total * 100, 1)}
        for k, v in evit_counts.items()
    }

    evitavel_total = sum(
        v for k, v in evit_counts.items()
        if k.startswith("EVITÁVEL")
    )
    results["evitabilidade"]["_total_evitavel"] = {
        "count": int(evitavel_total),
        "pct": round(evitavel_total / total * 100, 1)
    }

    # --- Análise temporal ---
    if "_data_parsed" in df.columns:
        temporal = {}
        df_with_date = df.dropna(subset=["_data_parsed"])
        if len(df_with_date) > 0:
            df_with_date = df_with_date.copy()
            df_with_date["_mes"] = df_with_date["_data_parsed"].dt.to_period("M").astype(str)
            monthly = df_with_date.groupby("_mes").size().to_dict()
            temporal["volume_mensal"] = {k: int(v) for k, v in monthly.items()}

            # Volume por categoria por mês
            monthly_cat = df_with_date.groupby(["_mes", "_macro_categoria"]).size().reset_index(name="count")
            temporal["categoria_mensal"] = []
            for _, row in monthly_cat.iterrows():
                temporal["categoria_mensal"].append({
                    "mes": row["_mes"],
                    "categoria": row["_macro_categoria"],
                    "count": int(row["count"])
                })

            # Dia da semana
            dow = df_with_date["_data_parsed"].dt.day_name().value_counts().to_dict()
            temporal["dia_semana"] = {k: int(v) for k, v in dow.items()}

            results["temporal"] = temporal

    # --- Análise por canal ---
    if "canal" in col_map and col_map["canal"] in df.columns:
        canal_data = {}
        canal_counts = df[col_map["canal"]].value_counts().to_dict()
        canal_data["distribuicao"] = {
            str(k): {"count": int(v), "pct": round(v / total * 100, 1)}
            for k, v in canal_counts.items()
        }

        # Categoria por canal
        canal_cat = df.groupby([col_map["canal"], "_macro_categoria"]).size().reset_index(name="count")
        canal_data["categoria_por_canal"] = []
        for _, row in canal_cat.iterrows():
            canal_data["categoria_por_canal"].append({
                "canal": str(row[col_map["canal"]]),
                "categoria": row["_macro_categoria"],
                "count": int(row["count"])
            })

        results["canal"] = canal_data

    # --- Eficiência ---
    if "tempo_resolucao" in col_map and col_map["tempo_resolucao"] in df.columns:
        try:
            tempo_col = col_map["tempo_resolucao"]
            df["_tempo_num"] = pd.to_numeric(df[tempo_col], errors="coerce")
            tempo_by_cat = df.groupby("_macro_categoria")["_tempo_num"].agg(["mean", "median", "count"]).reset_index()
            eficiencia = []
            for _, row in tempo_by_cat.iterrows():
                vol = int(row["count"])
                media = round(float(row["mean"]), 1) if pd.notna(row["mean"]) else None
                eficiencia.append({
                    "categoria": row["_macro_categoria"],
                    "tempo_medio": media,
                    "tempo_mediano": round(float(row["median"]), 1) if pd.notna(row["median"]) else None,
                    "volume": vol,
                    "custo_relativo": round(vol * (media or 0), 0)
                })
            eficiencia.sort(key=lambda x: x["custo_relativo"], reverse=True)
            results["eficiencia"] = eficiencia
        except Exception:
            pass

    # --- Gerar recomendações ---
    results["recomendacoes"] = generate_recommendations(results, total)

    return results


def generate_recommendations(results, total):
    """Gera recomendações priorizadas com base nas análises."""
    recs = []

    RECOMMENDATION_TEMPLATES = {
        ("INFORMACIONAL", "EVITÁVEL_SELF_SERVICE"): {
            "titulo": "Dashboard de rentabilidade e posição consolidada na área logada",
            "acao": "Melhorar a visualização de rentabilidade e posição consolidada na área logada do investidor, com filtros por fundo, período e benchmark. Incluir gráfico de evolução patrimonial e comparativo com CDI/IPCA.",
            "esforco": "Médio",
            "reducao_min": 30,
            "reducao_max": 50,
            "quick_win": False
        },
        ("INFORMACIONAL", "EVITÁVEL_UX"): {
            "titulo": "Redesign da tela de extrato com filtros e export",
            "acao": "Redesenhar a tela de extrato para incluir filtros por fundo, tipo de movimentação e período, com opção de exportar PDF/Excel. Muitos contatos informacionais vêm de dificuldade em encontrar dados na plataforma.",
            "esforco": "Médio",
            "reducao_min": 25,
            "reducao_max": 40,
            "quick_win": False
        },
        ("OPERACIONAL", "EVITÁVEL_PROATIVO"): {
            "titulo": "Notificações proativas de status de operações",
            "acao": "Implementar push notifications e e-mails automáticos para cada etapa da operação: confirmação de aplicação, cotização, liquidação de resgate (com D+N esperado), e status de portabilidade. A maioria dos contatos operacionais é 'cadê meu dinheiro?' — que pode ser prevenido com comunicação proativa.",
            "esforco": "Médio",
            "reducao_min": 35,
            "reducao_max": 55,
            "quick_win": False
        },
        ("OPERACIONAL", "EVITÁVEL_SELF_SERVICE"): {
            "titulo": "Status tracker de operações em tempo real",
            "acao": "Criar uma seção na área logada mostrando o status de cada operação pendente (aplicação, resgate, portabilidade) com timeline visual e previsão de conclusão.",
            "esforco": "Alto",
            "reducao_min": 30,
            "reducao_max": 45,
            "quick_win": False
        },
        ("TRIBUTARIO", "EVITÁVEL_PROATIVO"): {
            "titulo": "Comunicação proativa pré e pós come-cotas",
            "acao": "Enviar e-mail/push educativo 5 dias antes das datas de come-cotas (maio e novembro) explicando o mecanismo, o impacto esperado na cota, e que não representa perda real de rentabilidade. Pós-evento, enviar resumo do imposto recolhido por fundo.",
            "esforco": "Baixo",
            "reducao_min": 40,
            "reducao_max": 60,
            "quick_win": True
        },
        ("TRIBUTARIO", "EVITÁVEL_SELF_SERVICE"): {
            "titulo": "Central de informações tributárias e simulador de IR",
            "acao": "Criar seção dedicada a tributação na área logada com: FAQ sobre come-cotas (Lei 14.754/2023), simulador de IR por fundo, download do informe de rendimentos, e guia de declaração de IR.",
            "esforco": "Médio",
            "reducao_min": 25,
            "reducao_max": 40,
            "quick_win": False
        },
        ("TECNICO", "EVITÁVEL_SELF_SERVICE"): {
            "titulo": "Reset de senha self-service e troubleshooting automático",
            "acao": "Implementar fluxo de recuperação de senha/acesso totalmente self-service, com autenticação por SMS/e-mail. Adicionar página de status do sistema e troubleshooting básico para problemas comuns.",
            "esforco": "Baixo",
            "reducao_min": 40,
            "reducao_max": 65,
            "quick_win": True
        },
        ("TECNICO", "EVITÁVEL_AUTOMAÇÃO"): {
            "titulo": "Monitoramento proativo de erros e comunicação de incidentes",
            "acao": "Implementar monitoramento de erros que detecte problemas antes dos usuários e exiba banner na plataforma informando sobre instabilidades conhecidas, reduzindo contatos do tipo 'está fora do ar?'.",
            "esforco": "Médio",
            "reducao_min": 20,
            "reducao_max": 35,
            "quick_win": False
        },
        ("ONBOARDING", "EVITÁVEL_UX"): {
            "titulo": "Simplificação do fluxo de onboarding e upload de documentos",
            "acao": "Redesenhar o fluxo de cadastro com validação em tempo real, OCR para documentos, e checklist visual de pendências. Reduzir os motivos de contato 'como envio meu documento?' e 'meu cadastro está pendente'.",
            "esforco": "Alto",
            "reducao_min": 25,
            "reducao_max": 40,
            "quick_win": False
        },
        ("POS_VENDA", "REDUTÍVEL"): {
            "titulo": "Conteúdo educativo pós-investimento e expectativas de volatilidade",
            "acao": "Após aplicação em fundo, enviar série de e-mails educativos sobre o perfil de risco do fundo, expectativa de volatilidade, e horizonte recomendado. Reduz contatos de insatisfação após quedas de mercado.",
            "esforco": "Baixo",
            "reducao_min": 15,
            "reducao_max": 25,
            "quick_win": True
        },
        ("REGULATORIO", "REDUTÍVEL"): {
            "titulo": "Recadastro digital simplificado com pré-preenchimento",
            "acao": "Digitalizar o processo de atualização cadastral periódica com formulário pré-preenchido, confirmação em um clique para dados inalterados, e notificação antecipada do prazo.",
            "esforco": "Médio",
            "reducao_min": 20,
            "reducao_max": 35,
            "quick_win": False
        }
    }

    # Agregar por (macro, evitabilidade) para encontrar oportunidades
    motivos = results["distribuicao"].get("motivos_top20", [])
    seen_combos = set()

    for motivo_info in motivos:
        macro = motivo_info["macro"]
        count = motivo_info["count"]
        pct = motivo_info["pct"]

        # Buscar evitabilidade mais comum dessa macro
        # Simplificação: usar a classificação do motivo
        motivo_lower = motivo_info["motivo"].lower()
        evit = classify_evitability(macro, motivo_lower)

        combo = (macro, evit)
        if combo in seen_combos:
            continue
        seen_combos.add(combo)

        template = RECOMMENDATION_TEMPLATES.get(combo)
        if not template:
            continue

        # Calcular volume impactado (todos os contatos da macro-categoria)
        macro_info = results["distribuicao"]["macro"].get(macro, {})
        vol_impactado = macro_info.get("count", count)
        pct_impactado = macro_info.get("pct", pct)

        esforco_num = {"Baixo": 1, "Médio": 2, "Alto": 3}[template["esforco"]]
        reducao_media = (template["reducao_min"] + template["reducao_max"]) / 2
        score = round((vol_impactado * reducao_media / 100) / esforco_num, 1)

        recs.append({
            "titulo": template["titulo"],
            "categoria_alvo": macro,
            "volume_impactado": vol_impactado,
            "pct_do_total": pct_impactado,
            "classificacao": evit,
            "esforco": template["esforco"],
            "reducao_min": template["reducao_min"],
            "reducao_max": template["reducao_max"],
            "acao": template["acao"],
            "quick_win": template["quick_win"],
            "score": score
        })

    # Ordenar por score (quick wins primeiro entre empates)
    recs.sort(key=lambda r: (-int(r["quick_win"]), -r["score"]))

    return recs


# =============================================================================
# MAIN
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print("Uso: python contact_analyzer.py <arquivo_input> [--output <dir>]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_dir = "/home/claude"

    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_dir = sys.argv[idx + 1]

    os.makedirs(output_dir, exist_ok=True)

    # Ler arquivo
    print(f"Lendo arquivo: {input_file}")
    ext = os.path.splitext(input_file)[1].lower()
    if ext in [".xlsx", ".xls"]:
        df = pd.read_excel(input_file)
    elif ext == ".csv":
        # Tentar diferentes encodings e separadores
        for enc in ["utf-8", "latin-1", "cp1252"]:
            for sep in [",", ";", "\t"]:
                try:
                    df = pd.read_csv(input_file, encoding=enc, sep=sep)
                    if len(df.columns) > 1:
                        break
                except Exception:
                    continue
            else:
                continue
            break
    else:
        print(f"Formato não suportado: {ext}")
        sys.exit(1)

    print(f"Registros carregados: {len(df)}")
    print(f"Colunas encontradas: {list(df.columns)}")

    # Mapear colunas
    col_map = map_columns(df)
    print(f"Mapeamento de colunas: {json.dumps(col_map, ensure_ascii=False, indent=2)}")

    # Categorizar
    print("Categorizando contatos...")
    has_category = "categoria" in col_map and col_map["categoria"] in df.columns
    has_description = "descricao" in col_map and col_map["descricao"] in df.columns

    if has_category and has_description:
        # Usar categoria existente, mas revalidar com texto livre
        results = []
        for _, row in df.iterrows():
            cat_text = str(row[col_map["categoria"]]) if pd.notna(row[col_map["categoria"]]) else ""
            desc_text = str(row[col_map["descricao"]]) if pd.notna(row[col_map["descricao"]]) else ""
            macro_from_cat, motivo_from_cat = categorize_existing(cat_text)
            if macro_from_cat == "OUTRO" and desc_text:
                macro, motivo = categorize_text(desc_text)
            else:
                macro, motivo = macro_from_cat, motivo_from_cat
            results.append((macro, motivo))
    elif has_description:
        results = [categorize_text(str(row[col_map["descricao"]])) for _, row in df.iterrows()]
    elif has_category:
        results = [categorize_existing(str(row[col_map["categoria"]])) for _, row in df.iterrows()]
    else:
        print("AVISO: Nenhuma coluna de categoria ou descrição encontrada. Todos os contatos serão marcados como OUTRO.")
        results = [("OUTRO", "Sem dados para categorizar")] * len(df)

    df["_macro_categoria"] = [r[0] for r in results]
    df["_motivo"] = [r[1] for r in results]
    df["_evitabilidade"] = [
        classify_evitability(r[0], r[1].lower()) for r in results
    ]

    print(f"Categorização concluída. Distribuição macro:")
    for cat, count in df["_macro_categoria"].value_counts().items():
        print(f"  {cat}: {count} ({count/len(df)*100:.1f}%)")

    # Analisar
    print("Executando análises...")
    analysis = analyze_data(df, col_map)

    # Salvar resultados
    analysis_path = os.path.join(output_dir, "analysis_results.json")
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    print(f"Resultados salvos em: {analysis_path}")

    # Salvar dados categorizados
    categorized_path = os.path.join(output_dir, "dados_categorizados.csv")
    df.to_csv(categorized_path, index=False, encoding="utf-8-sig")
    print(f"Dados categorizados salvos em: {categorized_path}")

    # Resumo rápido
    print("\n" + "=" * 60)
    print("RESUMO DA ANÁLISE")
    print("=" * 60)
    print(f"Total de contatos: {analysis['resumo']['total_contatos']}")
    if analysis['resumo'].get('periodo_inicio'):
        print(f"Período: {analysis['resumo']['periodo_inicio']} a {analysis['resumo']['periodo_fim']}")

    evit = analysis.get("evitabilidade", {}).get("_total_evitavel", {})
    if evit:
        print(f"Contatos evitáveis: {evit['count']} ({evit['pct']}%)")

    print(f"\nRecomendações geradas: {len(analysis['recomendacoes'])}")
    for i, rec in enumerate(analysis["recomendacoes"][:5], 1):
        print(f"  {i}. [{rec['esforco']}] {rec['titulo']} — {rec['volume_impactado']} contatos ({rec['pct_do_total']}%)")
        if rec["quick_win"]:
            print(f"     ⚡ QUICK WIN")

    return analysis


if __name__ == "__main__":
    main()
