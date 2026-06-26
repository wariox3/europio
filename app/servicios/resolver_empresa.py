import re
import unicodedata

from rapidfuzz import fuzz, process

from app.modelos.empresa import Empresa

UMBRAL_MATCH = 85       # >= se considera coincidencia directa
UMBRAL_CANDIDATO = 60   # >= se ofrece como candidato a confirmar
MAX_PALABRAS_NOMBRE = 8  # más palabras = es una frase, no el nombre de una empresa

_SUFIJOS = re.compile(r"\b(sas|s\.a\.s|ltda|s\.a\.|sa)\b")


def normalizar(texto: str) -> str:
    texto = texto.lower().strip()
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    texto = _SUFIJOS.sub("", texto)
    return re.sub(r"\s+", " ", texto).strip()


def resolver_empresa(texto_usuario: str, empresas: list[Empresa]) -> dict:
    """Devuelve {"match": empresa_id|None, "candidatos": [empresa_id, ...]}.

    Cada nombre y cada alias compite por separado en el fuzzy match; el
    resultado se mapea de vuelta al id de la empresa.
    """
    candidatos_texto: dict[int, str] = {}   # clave única -> texto normalizado
    clave_a_empresa: dict[int, int] = {}    # clave única -> empresa_id
    idx = 0
    for e in empresas:
        for variante in [e.nombre, *(e.alias or "").split(",")]:
            v = normalizar(variante)
            if not v:
                continue
            candidatos_texto[idx] = v
            clave_a_empresa[idx] = e.id
            idx += 1

    if not candidatos_texto:
        return {"match": None, "candidatos": []}

    texto_norm = normalizar(texto_usuario)
    # Si el usuario escribió una frase larga (p. ej. una consulta de soporte en
    # vez del nombre), no la tratamos como nombre de empresa: evita falsos
    # positivos del fuzzy match contra textos largos.
    if len(texto_norm.split()) > MAX_PALABRAS_NOMBRE:
        return {"match": None, "candidatos": []}

    # Coincidencia exacta: si el texto es idéntico a un nombre o alias, resuelve
    # sin pasar por el fuzzy. El token_ratio da 100 también cuando el texto es
    # subconjunto de otra variante (p. ej. el alias "eurovic" contra "eurovic
    # cali"), así que la igualdad literal es lo único que distingue cuántas
    # empresas coinciden de verdad: una -> match; varias (alias compartido) ->
    # candidatos para desambiguar.
    exactas: list[int] = []
    for clave, v in candidatos_texto.items():
        if v == texto_norm:
            empresa_id = clave_a_empresa[clave]
            if empresa_id not in exactas:
                exactas.append(empresa_id)
    if len(exactas) == 1:
        return {"match": exactas[0], "candidatos": []}
    if len(exactas) > 1:
        return {"match": None, "candidatos": exactas}

    # token_ratio (no WRatio): no usa partial_ratio, que premiaba que el nombre
    # corto apareciera como subcadena dentro de una frase larga e inflaba el score.
    # limit alto: con empresas que comparten alias, un tope bajo dejaría fuera
    # coincidencias válidas que empatan en score.
    resultados = process.extract(
        texto_norm, candidatos_texto, scorer=fuzz.token_ratio,
        limit=len(candidatos_texto),
    )
    if not resultados:
        return {"match": None, "candidatos": []}

    # resultados: lista de (texto, score, clave)
    mejor_score = resultados[0][1]
    if mejor_score >= UMBRAL_MATCH:
        # Varias empresas pueden empatar en el mejor score (p. ej. comparten
        # alias). Solo auto-resolvemos si una única empresa lo alcanza; si hay
        # empate, las ofrecemos como candidatos para que el usuario desambigüe.
        empresas_match: list[int] = []
        for _, score, clave in resultados:
            if score == mejor_score:
                empresa_id = clave_a_empresa[clave]
                if empresa_id not in empresas_match:
                    empresas_match.append(empresa_id)
        if len(empresas_match) == 1:
            return {"match": empresas_match[0], "candidatos": []}
        return {"match": None, "candidatos": empresas_match}

    candidatos: list[int] = []
    for _, score, clave in resultados:
        if score >= UMBRAL_CANDIDATO:
            empresa_id = clave_a_empresa[clave]
            if empresa_id not in candidatos:
                candidatos.append(empresa_id)
    return {"match": None, "candidatos": candidatos}
