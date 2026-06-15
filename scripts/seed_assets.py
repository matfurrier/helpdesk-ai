#!/usr/bin/env python3
"""Seed IT asset inventory — notebooks and smartphones from spreadsheet export."""
from __future__ import annotations

import json
import re
import sys
from datetime import date

import psycopg2

DSN = "host=helpdesk-postgres dbname=helpdesk user=helpdesk password=kzbNf6eGaZ_ck6kL1evCN9uw"


def _date(s: str) -> date | None:
    if not s:
        return None
    s = s.strip()
    if s in ("(S/D)", "S/D", "?", ""):
        return None
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def _tag(s: str) -> str | None:
    if not s:
        return None
    s = s.strip()
    if s.upper() in ("(SEM PLACA)", "SEM PLACA", "BAIXADO", ""):
        return None
    return s


def _bool(s: str) -> bool:
    return s.strip().upper() in ("OK",)


def _brand(modelo: str) -> tuple[str | None, str]:
    for b in ("Dell", "Samsung", "Lenovo", "Asus", "HP", "Apple"):
        if modelo.strip().lower().startswith(b.lower()):
            return b, modelo.strip()
    if "samsung" in modelo.lower() or "ultrabook" in modelo.lower():
        return "Samsung", modelo.strip()
    if modelo.strip().lower().startswith("inspiron"):
        return "Dell", "Dell " + modelo.strip()
    return None, modelo.strip()


def _nb_status(usuario: str) -> str:
    u = usuario.strip().upper()
    if u == "BAIXADO":
        return "retired"
    if u == "FURTO":
        return "lost"
    return "active"


def _nb_holder(usuario: str, setor: str) -> tuple[str | None, str | None]:
    skip = {"ARMÁRIO", "BAIXADO", "FURTO", ""}
    u = usuario.strip()
    s = setor.strip()
    return (None if u.upper() in skip else u, None if s.upper() in skip else s)


def _phone(s: str) -> str | None:
    s = s.strip()
    if s in ("", "(00)00000-0000", "?"):
        return None
    return s


# Notebooks: (modelo, nome_pc, usuario, setor, av, fi, tr, placa, so, proc, ram, hd, cond, aquisicao)
NOTEBOOKS: list[tuple[str, ...]] = [
    # === ARMÁRIO ===
    ("Dell Inspiron 7460","Bateria ruim","ARMÁRIO","ARMÁRIO","","","","001.759","Windows 10 PRO","Intel Core I5 - 7200U","8GB","1TB","OK",""),
    ("Dell Inspiron 15 3000 (3501)","Mousepad ruim","ARMÁRIO","ARMÁRIO","","","","001.807","Windows 10 PRO","Intel Core I7 - 8550U","8GB","480SSD","OK",""),
    ("Dell Inspiron 15 5000","","ARMÁRIO","ARMÁRIO","","","","001.812","Windows 10 PRO","Intel Core I7 - 8550U","8GB","1TB","Ótimo",""),
    ("Dell Inspiron 14 5468 (preto)","","ARMÁRIO","ARMÁRIO","","","","001.823","Windows 10 PRO","Intel Core I7 - 5500U","8GB","480SSD","Ótimo",""),
    ("Dell Inspiron 5448 (prata)","","ARMÁRIO","ARMÁRIO","","","","002.169","Windows 10 PRO","Intel Core I7 - 5500U","8GB","480SSD","Ótimo",""),
    ("Dell Inspiron 14 P74G","","ARMÁRIO","ARMÁRIO","","","","002.350","Windows 10 PRO","","","","",""),
    ("Dell Inspiron 15 3000 (3501)","","ARMÁRIO","ARMÁRIO","","","","002.483","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo",""),
    ("Dell Inspiron 15 3000 (3501)","","ARMÁRIO","ARMÁRIO","","","","002.485","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo",""),
    ("Dell Inspiron 15 3000 (3501)","","ARMÁRIO","ARMÁRIO","","","","002.501","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo",""),
    ("Dell Inspiron 15 3000 (3501)","","ARMÁRIO","ARMÁRIO","","","","002.503","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo",""),
    ("Dell Inspiron 15 3000 (3501)","","ARMÁRIO","ARMÁRIO","","","","002.514","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo",""),
    ("Dell Inspiron 15 3000 (3501)","","ARMÁRIO","ARMÁRIO","","","","002.519","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo",""),
    ("Dell Inspiron 15 5510","Teclas ruim","ARMÁRIO","ARMÁRIO","","","","003.240","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","OK",""),
    ("Dell Inspiron 15 3530","","ARMÁRIO","ARMÁRIO","","","","003.946","Windows 11 PRO","Intel i5 13ª","16GB","502 SSD","Ótimo",""),
    ("Dell Inspiron 15 3530","","ARMÁRIO","ARMÁRIO","","","","003.947","Windows 11 PRO","Intel i5 13ª","16GB","503 SSD","Ótimo",""),
    ("Dell Inspiron 15 3530","","ARMÁRIO","ARMÁRIO","","","","003.950","Windows 11 PRO","Intel i5 13ª","16GB","506 SSD","Ótimo",""),
    # === BAIXADO ===
    ("Dell Latitude 3440","","BAIXADO","BAIXADO","","","","001.734","","","","","",""),
    ("Dell Vostro 5480","","BAIXADO","BAIXADO","","","","001.737","","","","","",""),
    ("Dell Inspiron 7347","","BAIXADO","BAIXADO","","","","001.739","","","","","",""),
    ("Dell Inspiron 7347","","BAIXADO","BAIXADO","","","","001.741","","","","","",""),
    ("Dell Inspiron 3420","","BAIXADO","BAIXADO","","","","001.743","","","","","",""),
    ("Samsung","","BAIXADO","BAIXADO","","","","001.744","","","","","",""),
    ("Samsung Ultrabook","","BAIXADO","BAIXADO","","","","001.744b","","","","","",""),
    ("Asus K46CA","","BAIXADO","BAIXADO","","","","001.746","","","","","",""),
    ("Samsung Ultrabook","","BAIXADO","BAIXADO","","","","001.748","","","","","",""),
    ("Dell Inspiron 5468","","BAIXADO","BAIXADO","","","","001.751","","","","","",""),
    ("Dell Vostro 5480","","BAIXADO","BAIXADO","","","","001.755","","","","","",""),
    ("Dell Inspiron 7460","","BAIXADO","BAIXADO","","","","001.761","","","","","",""),
    ("Dell Inspiron 5448","","BAIXADO","BAIXADO","","","","001.763","","","","","",""),
    ("Dell Latitude 3440","","BAIXADO","BAIXADO","","","","001.767","","","","","",""),
    ("Dell Inspiron 15 3000 (preto)","","BAIXADO","BAIXADO","","","","001.769","","","","","",""),
    ("Dell Inspiron 5420","","BAIXADO","BAIXADO","","","","001.771","","","","","",""),
    ("Dell Latitude 3440","","BAIXADO","BAIXADO","","","","001.771b","","","","","",""),
    ("Dell Inspiron 5468","","BAIXADO","BAIXADO","","","","001.775","","","","","",""),
    ("Lenovo Z400","","BAIXADO","BAIXADO","","","","001.778","","","","","",""),
    ("Dell Inspiron 5468","","BAIXADO","BAIXADO","","","","001.786","","","","","",""),
    ("Dell Vostro 5480","","BAIXADO","BAIXADO","","","","001.793","","","","","",""),
    ("Dell Inspiron 15 5000","","BAIXADO","BAIXADO","","","","001.808","","","","","",""),
    ("Dell Inspiron 5458","","BAIXADO","BAIXADO","","","","001.817","","","","","",""),
    ("Dell Inspiron 5458","","BAIXADO","BAIXADO","","","","001.818","","","","","",""),
    ("Lenovo Z40-70","","BAIXADO","BAIXADO","","","","001.821","","","","","",""),
    ("Asus S46CA","","BAIXADO","BAIXADO","","","","001.825","","","","","",""),
    ("Dell Inspiron 5458","","BAIXADO","BAIXADO","","","","001.827","","","","","",""),
    ("Dell Inspiron 15 5000","","BAIXADO","BAIXADO","","","","001.830","","","","","",""),
    ("Dell Inspiron 3442","","BAIXADO","BAIXADO","","","","001.831","","","","","",""),
    ("Dell Inspiron 14 5468","","BAIXADO","BAIXADO","","","","001.833","","","","","",""),
    ("Dell Inspiron 5468","","BAIXADO","BAIXADO","","","","001.834","","","","","",""),
    ("Dell Inspiron 3567","","BAIXADO","BAIXADO","","","","001.836","","","","","",""),
    ("Lenovo Z400","","BAIXADO","BAIXADO","","","","001.837","","","","","",""),
    ("Asus S400CA","","BAIXADO","BAIXADO","","","","001.918","","","","","",""),
    ("Dell Inspiron 14 5482","","BAIXADO","BAIXADO","","","","002.115","","","","","",""),
    ("Dell Inspiron 5590","","BAIXADO","BAIXADO","","","","002.255","","","","","",""),
    ("Dell Inspiron 5590 (prata)","","BAIXADO","BAIXADO","","","","002.349","","","","","",""),
    ("Dell Inspiron 15 3000 (3501)","","BAIXADO","BAIXADO","","","","002.509","","","","","",""),
    ("Dell Inspiron 15 3000 (3501)","","BAIXADO","BAIXADO","","","","002.515","","","","","",""),
    ("Dell Inspiron 15 3000 (3501)","","BAIXADO","BAIXADO","","","","002.521","","","","","",""),
    ("Dell Inspiron 15 3000 (3501)","","BAIXADO","BAIXADO","","","","002.530","","","","","",""),
    ("Dell Inspiron 3511","","BAIXADO","BAIXADO","","","","003.200","","","","","",""),
    ("Dell Inspiron 15 5510","","BAIXADO","BAIXADO","","","","003.244","","","","","",""),
    ("Samsung","","BAIXADO","BAIXADO","","","","101.024","","","","","",""),
    ("Samsung Ultrabook","","BAIXADO","BAIXADO","","","","(SEM PLACA)","","","","","",""),
    ("Asus S400CA","","BAIXADO","BAIXADO","","","","(SEM PLACA)","","","","","",""),
    ("Dell Inspiron 3583","","BAIXADO","BAIXADO","","","","000.492","","","","","",""),
    # === FURTO ===
    ("Dell Inspiron 5468","","FURTO","BAIXADO","","","","001.835","","","","","",""),
    ("Dell Inspiron 3583","","FURTO","BAIXADO","","","","002.212","","","","","",""),
    ("Dell Inspiron 15 3000 (3501)","","FURTO","BAIXADO","","","","002.502","","","","","",""),
    ("Dell Inspiron 15 3000 (3501)","","FURTO","BAIXADO","","","","002.537","","","","","",""),
    # === ATIVO - Comercial ===
    ("Dell Inspiron 15 5510","DSCOM014","Beatriz Rezende","Comercial","OK","OK","OK","003.223","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 5510","DSCOM015","Fernanda Lemos","Comercial","OK","OK","OK","002.170","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 3000 (3501)","DSFIS006","Guilherme Silva","Comercial","OK","OK","OK","002.500","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 5510","DSCOM012","Winderson Bahu","Comercial","OK","OK","OK","003.229","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    # === ATIVO - Compras ===
    ("Dell Inspiron 15 5510","DSCOMP028","Arnon Canales","Compras","OK","OK","OK","003.219","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 5510","DSFIN029","Carlos Watanabe","Compras","OK","OK","OK","003.224","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo",""),
    ("Dell Inspiron 15 5510","DSFIN024","Fernando Alencar","Compras","OK","OK","OK","003.238","Windows 10 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 5510","DSCOMP002","Karina Silva","Compras","OK","OK","OK","003.237","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 5510","DSFIN026","Luiz Henrique","Compras","OK","OK","OK","003.235","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    # === ATIVO - Contabilidade ===
    ("Dell Inspiron 15 3000 (3501)","DSFIS009","Ana Flavia Bueno","Contabilidade","OK","OK","OK","002.523","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 3530","DSFIS008","Andressa Barbosa","Contabilidade","OK","OK","OK","003.949","Windows 11 PRO","Intel i5 13ª","16GB","505 SSD","Ótimo",""),
    ("Dell Inspiron 15 5510","DSFIS013","Bianca Almeida","Contabilidade","OK","OK","OK","003.227","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo",""),
    ("Dell Inspiron 15 5510","DSFIS014","Jessica Mota","Contabilidade","OK","OK","OK","003.222","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 5510","DSFIS012","Maikon Gouveia","Contabilidade","OK","OK","OK","003.210","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 5510","DSFIS011","Renato Sobrinho","Contabilidade","OK","OK","OK","003.234","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    # === ATIVO - Copa admin ===
    ("Dell Inspiron 15 7000","DSFUN004","Funcionários Copa admin","Copa admin","OK","OK","OK","001.795","Windows 10 PRO","Intel Core I7 - 8550U","16GB","480 SSD + 1TB","Ótimo","28/02/2019"),
    # === ATIVO - Cozinha ===
    ("Dell Inspiron 5468","DSFUN007","Cozinha - 1º salão","Cozinha","OK","OK","OK","(SEM PLACA)","Windows 10 PRO","Intel Core I5 - 7200U","8GB","256SSD","Bom",""),
    ("Dell Inspiron 5468","DSFUN008","Cozinha - 2º salão","Cozinha","OK","OK","OK","001.816","Windows 10 PRO","Intel Core I5 - 7200U","4GB","1TB","Bom","12/06/2018"),
    ("Dell Inspiron 3511","DSREF007","Cozinha - Dispensa","Cozinha","OK","OK","OK","003.207","Windows 11 PRO","Intel Core i5- 1135g7","8GB","SSD256","Ótimo","10/10/2022"),
    # === ATIVO - Diretoria ===
    ("Dell Latitude 5320","DSDIR006","Flavio Matarazzo","Diretoria","OK","OK","OK","003.199","Windows 11 PRO","Intel Core i5- 1145g7","16GB","512SSD","Ótimo",""),
    ("Dell Latitude 5320","DSGER008","Marco Lopes","Diretoria","OK","OK","OK","003.198","Windows 11 PRO","Intel Core i5- 1145g7","16GB","SSD256","Ótimo","10/10/2022"),
    ("Dell Inspiron 15 5510","","Marco Lopes","Diretoria","OK","OK","OK","003.242","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 5510","DSGER019","Rogerio Tesser","Diretoria","OK","OK","OK","003.211","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 3530","DSGER021","Rogerio Tesser","Diretoria","OK","OK","OK","003.945","Windows 11 PRO","Intel i5 13ª","16GB","501 SSD","Ótimo",""),
    # === ATIVO - Externo ===
    ("Dell Inspiron 3583 (preto)","DSEXT141","Antônio Santos","Externo","OK","OK","OK","002.211","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD + 1TB","Ótimo","20/08/2020"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT198","Braullio Siqueira","Externo","OK","OK","OK","002.488","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 5468","DSEXT124","Caique Alves","Externo","OK","OK","OK","002.266","Windows 10 PRO","Intel Core I5 - 7200U","4GB","240SSD","Bom","12/06/2018"),
    ("Dell Inspiron 3583","DSEXT002","Camila Vasconcelos","Externo","OK","OK","OK","002.215","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD + 1TB","Ótimo",""),
    ("Dell Inspiron 15 3000 (3501)","DSEXT144","Claudio Negrão","Externo","OK","OK","OK","002.532","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 3583","DSEXT164","Cleto","Externo","OK","OK","OK","002.269","Windows 10 PRO","Intel Core I7 - 8565U","8GB","128 SSD + 1TB","Ótimo","27/10/2020"),
    ("Dell Inspiron 15 5000","DSEXT182","Diego Rezende","Externo","OK","OK","OK","001.809","Windows 10 PRO","Intel Core I7 - 8550U","8GB","1TB","Ótimo","23/05/2019"),
    ("Dell Vostro 3500","DSEXT193","Edinei Moreira","Externo","OK","OK","OK","002.357","Windows 10 PRO","Intel Core I5 - 1135g7","8GB","256 SSD","Ótimo","24/03/2021"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT137","Eduardo Zanatta","Externo","OK","OK","OK","002.490","Windows 10 PRO","Intel Core I5- 1035G2","8GB","480 SSD","Ótimo","12/07/2024"),
    ("Dell Inspiron 14 5482","DSEXT133","Eloir Junior","Externo","OK","OK","OK","002.168","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD","Ótimo","07/12/2019"),
    ("Dell Vostro 3500","DSEXT178","Emerson Lopes","Externo","OK","OK","OK","002.358","Windows 10 PRO","Intel Core I5 - 1135g7","8GB","256 SSD","Regular","24/03/2021"),
    ("Dell Inspiron 5468 (preto)","DSEXT160","Erivelson Sembrebom","Externo","OK","OK","OK","001.919","Windows 10 PRO","Intel Core I7 - 8550U","8GB","1TB","Ótimo",""),
    ("Dell Inspiron 15 3000 (3501)","DSEXT190","Felipe Rodrigues","Externo","OK","OK","OK","002.486","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo",""),
    ("Dell Inspiron 5590","DSEXT135","Gilmar Alves","Externo","OK","OK","OK","002.204","Windows 10 PRO","Intel Core I7 - 10510U","8GB","256SSD","Ótimo",""),
    ("Dell Inspiron 3583 (prata)","DSEXT177","Gilmércio Pacheco","Externo","OK","OK","OK","002.218","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD + 1TB","Ótimo","20/08/2020"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT069","Guilherme Alves","Externo","OK","OK","OK","002.516","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 5468","DSEXT063","Guilherme Oliveira Junior","Externo","OK","OK","OK","001.819","Windows 10 PRO","Intel Core I5 - 7200U","4GB","480SSD","Bom","12/06/2018"),
    ("Dell Inspiron 5468 (preto)","DSEXT149","Gustavo Fabbrin","Externo","OK","OK","OK","001.822","Windows 10 PRO","Intel Core I5 - 7200U","4GB","1TB","Bom","20/01/2018"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT170","Gustavo Vicentin","Externo","OK","OK","OK","002.520","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT189","Hewerton Magalhaes","Externo","OK","OK","OK","002.491","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT180","Iago Almeida","Externo","OK","OK","OK","002.535","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 3583 (prata)","DSEXT186","Isabel Castro","Externo","OK","OK","OK","002.268","Windows 10 PRO","Intel Core I7 - 8565U","8GB","SSD480","OK",""),
    ("Dell Inspiron 15 3000 (3501)","DSEXT006","Isabelle Vilarino","Externo","OK","OK","OK","002.513","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT199","Ivan Favretto","Externo","OK","OK","OK","002.497","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT100","Iziel Biasi","Externo","OK","OK","OK","002.496","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 3511","DSEXT132","Jace","Externo","OK","OK","OK","001.784","Windows 11 PRO","Intel Core i5- 1135g7","8GB","SSD256","Ótimo","10/10/2022"),
    ("Dell Inspiron 3583","DSEXT111","Jadson Azevedo","Externo","OK","OK","OK","002.213","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD + 1TB","Ótimo","20/08/2020"),
    ("Dell Inspiron 3583","DSEXT065","Jaqueson Rupp","Externo","OK","OK","OK","002.263","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD + 1TB","Ótimo","20/08/2020"),
    ("Dell Inspiron 7460 (prata)","DSEXT076","Jean Batista","Externo","OK","OK","OK","001.787","Windows 10 PRO","Intel Core I5 - 7200U","8GB","500GB","Bom",""),
    ("Dell Inspiron 3567","DSEXT183","Jeferson Branco","Externo","OK","OK","OK","001.777","Windows 10 PRO","Intel Core I5 - 8200U","8GB","1TB","OK",""),
    ("Dell Inspiron 3511","DSEXT120","João Prestes","Externo","OK","OK","OK","003.206","Windows 11 PRO","Intel Core i5- 1135g7","8GB","SSD256","Ótimo","10/10/2022"),
    ("Dell Inspiron 3583 (preto)","DSEXT118","João Victor","Externo","OK","OK","OK","002.210","Windows 10 PRO","Intel Core I7 - 8565U","8GB","SSD 240 + 1TB","Ótimo",""),
    ("Dell Inspiron 15 3000 (3501)","DSEXT127","Lorem","Externo","OK","OK","OK","002.489","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 5468 (preto)","DSEXT037","Lucas Amorim","Externo","OK","OK","OK","001.791","Windows 10 PRO","Intel Core I5 - 7200U","8GB","1TB","Ótimo","28/02/2018"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT005","Lucas Fernandes","Externo","OK","OK","OK","002.508","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo",""),
    ("Dell Inspiron 15 3000 (3501)","DSEXT126","Luiz Cera","Externo","OK","OK","OK","002.495","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 5468 (prata)","DSEXT032","Luiz França","Externo","OK","OK","OK","001.789","Windows 10 PRO","Intel Core I5 - 7200U","8GB","1TB","Bom",""),
    ("Dell Inspiron 15 3000 (3501)","DSEXT066","Luiz Kaliton Pereira","Externo","OK","OK","OK","002.476","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo",""),
    ("Dell Inspiron 15 5000","DSEXT150","Maikol Fornari","Externo","OK","OK","OK","001.810","Windows 10 PRO","Intel Core I7 - 8550U","8GB","1TB","Ótimo","23/05/2019"),
    ("Dell Inspiron 3583 (preto)","DSEXT175","Manuella Saito","Externo","OK","OK","OK","002.208","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD + 1TB","Ótimo","20/08/2020"),
    ("Dell Inspiron 5468 (prata)","DSEXT026","Marcus Vinicius","Externo","OK","OK","OK","002.271","Windows 10 PRO","Intel Core I5 - 7200U","4GB","1TB","Bom","23/03/2018"),
    ("Dell Inspiron 3583 (prata)","DSEXT130","Marcus Vinicius","Externo","OK","OK","OK","002.271b","Windows 10 PRO","Intel Core I7 - 8565U","8GB","128 SSD + 1TB","Ótimo","27/10/2020"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT033","Mateus Abreu","Externo","OK","OK","OK","002.533","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT187","Mateus Belle","Externo","OK","OK","OK","002.507","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo",""),
    ("Dell Inspiron 15 3000 (3501)","DSEXT188","Mateus Hunoff","Externo","OK","OK","OK","002.477","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT201","Matheus Silva","Externo","OK","OK","OK","002.517","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 3583 (prata)","DSEXT176","Mauro Dourado","Externo","OK","OK","OK","002.264","Windows 10 PRO","Intel Core I7 - 8565U","8GB","128 SSD + 1TB","Ótimo",""),
    ("Dell Inspiron 3583 (preto)","DSEXT059","Michael Douglas","Externo","OK","OK","OK","002.216","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD + 1TB","Ótimo","20/08/2020"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT121","Paula Oliosi","Externo","OK","OK","OK","002.510","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 3442","DSEXT009","Paulo Bit","Externo","OK","OK","OK","001.828","Windows 10 PRO","Intel Core i3 - 4005U","4GB","500GB","Regular",""),
    ("Dell Inspiron 15 5510","DSEXT045","Paulo Martins","Externo","OK","OK","OK","003.220","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 3000 (prata)","DSEXT027","Paulo Roberto","Externo","OK","OK","OK","001.829","Windows 10 PRO","Intel Core I5 - 7200U","8GB","1TB","Ótimo","28/02/2018"),
    ("Dell Inspiron 15 5510","DSEXT029","Renato Belisário","Externo","OK","OK","OK","003.228","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT200","Rhaif Silva","Externo","OK","OK","OK","002.499","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT165","Rodolfo Medeiros","Externo","OK","OK","OK","002.493","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 5510","DSEXT003","Romeu","Externo","OK","OK","OK","003.225","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT192","Sara Kamer","Externo","OK","OK","OK","002.518","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo",""),
    ("Dell Inspiron 3583 (preto)","DSEXT097","Scarlet Alves","Externo","OK","OK","OK","002.206","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD + 1TB","Ótimo",""),
    ("Dell Inspiron 15 3000 (3501)","DSEXT197","Silney","Externo","OK","OK","OK","002.481","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo",""),
    ("Dell Inspiron 5590","DSEXT196","Tatiane Pocas","Externo","OK","OK","OK","002.265","Windows 10 PRO","Intel Core I7 - 10510U","8GB","256SSD","Ótimo",""),
    ("Dell Inspiron 15 3000 (3501)","DSEXT122","Tiarles Renan Dal Pai","Externo","OK","OK","OK","002.522","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT191","Valtezer Hunhoff","Externo","OK","OK","OK","002.505","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Vostro (preto)","DSEXT171","Vitor Ferre Pires","Externo","OK","OK","OK","002.262","Windows 10 PRO","Intel Core I7 - 8565U","8GB","240SSD + 1TB","Ótimo",""),
    ("Dell Inspiron 3583","DSEXT181","Wagner Furlanetto","Externo","OK","OK","OK","002.267","Windows 10 PRO","Intel Core I7 - 8565U","8GB","128 SSD + 1TB","Ótimo",""),
    ("Dell Inspiron 3583 (preto)","DSEXT164","Wellington","Externo","OK","OK","OK","002.209","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD + 1TB","Ótimo","20/08/2020"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT004","Wesley Oliveira","Externo","OK","OK","OK","002.494","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo",""),
    ("Dell Inspiron 15 3000 (3501)","DSEXT194","William Pozzobon","Externo","OK","OK","OK","002.536","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 P75F","DSEXT145","Witer Moreira","Externo","OK","OK","OK","002.219","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD","Ótimo",""),
    # === ATIVO - Externo P&D ===
    ("Dell Inspiron 15 3000 (3501)","DSEXT154","Fabio Peron","Externo - P&D","OK","OK","OK","002.504","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 3583","DSEXT131","Filipe Mendes","Externo - P&D","OK","OK","OK","002.205","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD + 1TB","Ótimo","20/08/2020"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT001","Irineu Kuhn","Externo - P&D","OK","OK","OK","002.534","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 3583","DSEXT158","Jonathan Gauze","Externo - P&D","OK","OK","OK","002.214","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD + 1TB","Ótimo","20/08/2020"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT179","Marcio Fernandes","Externo - P&D","OK","OK","OK","002.492","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 3583","DSEXT136","Marcos Vinicius","Externo - P&D","OK","OK","OK","002.270","Windows 10 PRO","Intel Core I7 - 8565U","8GB","128 SSD + 1TB","Ótimo",""),
    ("Dell Inspiron 15 3000 (3501)","DSEXT136","Marcos Vinicius Rodrigues","Externo - P&D","OK","OK","OK","002.511","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 3583 (preto)","DSEXT047","Matheus Castanho","Externo - P&D","OK","OK","OK","002.207","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD + 1TB","OK","20/08/2020"),
    ("Dell Inspiron 15 3000 (3501)","DSEXT115","Rafael Cardoso","Externo - P&D","OK","OK","OK","002.526","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo",""),
    # === ATIVO - Financeiro ===
    ("Dell Inspiron 15 5510","DSFIN025","Daniel Garcia","Financeiro","OK","OK","OK","002.167","Windows 10 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 5510","DSFIN026","Denner Soares","Financeiro","OK","OK","OK","003.246","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 3530","DSFIN027","Laila Sena","Financeiro","OK","OK","OK","003.951","Windows 11 PRO","Intel i5 13ª","16GB","507 SSD","Ótimo",""),
    ("Dell Inspiron 15 3000 (3501)","DSCOM008","Matheus Estevão","Financeiro","OK","OK","OK","002.525","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 5510","DSFIN024","Michael Silva","Financeiro","OK","OK","OK","002.166","Windows 10 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    # === ATIVO - Laboratório ===
    ("Dell Inspiron 15 3000 (3501)","DSLAB007","Adervaldo","Laboratório","OK","OK","OK","002.531","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 3000 (3501)","DSLAB014","Emannuel","Laboratório","OK","OK","OK","002.512","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 5510","DSLAB016","Everson Sales","Laboratório","OK","OK","OK","003.218","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 14 5482","DSLAB009","Laboratorio (2º andar)","Laboratório","OK","OK","OK","002.120","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD","Ótimo","07/12/2019"),
    ("Dell Inspiron 15 5510","DSLAB015","Letícia Oliveira","Laboratório","OK","OK","OK","003.221","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 3000 (3501)","DSFIN017","Marcela Amancio","Laboratório","OK","OK","OK","002.527","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 3000 (3501)","DSLAB013","Mayara Galvao","Laboratório","OK","OK","OK","002.484","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 3583","DSLAB016","Resíduos / Aprendiz","Laboratório","OK","OK","OK","002.217","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD + 1TB","Ótimo","28/02/2018"),
    ("Dell Inspiron 15 3000 (3501)","DSLAB014","Valdeir Santos","Laboratório","OK","OK","OK","002.487","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    # === ATIVO - Lavanderia ===
    ("Dell Inspiron 5468 (preto)","DSFUN008","Funcionários Lavanderia","Lavanderia","OK","OK","OK","001.765","Windows 10 PRO","Intel Core I5 - 7200U","8GB","480SSD","Ótimo","13/04/2018"),
    # === ATIVO - Logística ===
    ("Dell Vostro 3500","DSEXP002","Anderson Silva","Logistica","OK","OK","OK","002.359","Windows 10 PRO","Intel Core I5 - 1135g7","8GB","256 SSD","Ótimo","24/03/2021"),
    ("Dell Inspiron 5468","DSEXP012","Aprendiz","Logistica","OK","OK","OK","001.738","Windows 10 PRO","Intel Core I5 - 7200U","4GB","240SSD","Bom",""),
    ("Dell Inspiron 15 3000 (3501)","DSEXP011","Bruno Lima","Logistica","OK","OK","OK","001.757","Windows 10 PRO","Intel Core I5 - 3210M","8GB","500GB","Bom",""),
    ("Dell Inspiron 15 3000 (3501)","DSEXP009","Cleber Padilha","Logistica","OK","OK","OK","002.498","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Vostro 3500","DSEXP008","Eliane Cachione","Logistica","OK","OK","OK","002.362","Windows 10 PRO","Intel Core I5 - 1135g7","8GB","256 SSD","Ótimo","24/03/2021"),
    ("Dell Inspiron 15 3530","DSEXP013","Logistica - almoxarifado","Logistica/almoxarifado","OK","OK","OK","003.848","Windows 10 PRO","Intel Core I5 - 8200U","8GB","500GB","Ótimo",""),
    # === ATIVO - Manutenção ===
    ("Dell Inspiron 3511","DSMAN014","Alex de Paula","Manutenção","OK","OK","OK","003.209","Windows 11 PRO","Intel Core i5- 1135g7","8GB","SSD256","Ótimo","10/10/2022"),
    ("Dell Inspiron 15 3000 (3501)","DSMAN012","Gabryell Oliveira","Manutenção","OK","OK","OK","002.480","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Vostro 3500","DSMAN002","Julio Barbosa","Manutenção","OK","OK","OK","002.361","Windows 10 PRO","Intel Core I5 - 1135g7","8GB","256 SSD","Ótimo","24/03/2021"),
    ("Dell Inspiron 15 3000 (3501)","DSMAN013","Sidnei Rossato","Manutenção","OK","OK","OK","001.805","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    # === ATIVO - MKT ===
    ("Dell Inspiron 15 5510","DSMKT017","Ana Carolina Felde","MKT","OK","OK","OK","001.780","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo",""),
    ("Dell G15 5520","DSMKT016","Guilherme Tissiano","MKT","OK","OK","OK","003.444","Windows 10 PRO","Intel Core i7-11800H","16GB","SSD512","Ótimo","09/11/2021"),
    ("Dell Inspiron 15 5510","DSMKT018","Julia Silva","MKT","OK","OK","OK","003.214","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo",""),
    ("Dell G15 5530","DSMKT015","Karina Ferreira","MKT","OK","OK","OK","003.833","Windows 11 PRO","Intel Core I7 13650HX","16GB","1TB","Ótimo",""),
    ("Dell Inspiron 14 7440","DSGER020","Ricardo H.","MKT","OK","OK","OK","003.819","Windows 10 PRO","Intel Core I7 - 5500U","8GB","1TB","Bom",""),
    ("Dell G15 5511","DSMKT010","Taynan Santos","MKT","OK","OK","OK","003.430","Windows 10 PRO","Intel Core i7-11800H","16GB","SSD512","Ótimo","09/11/2021"),
    ("Dell Inspiron 15 5510","DSMKT012","Thiago Pereira","MKT","OK","OK","OK","003.217","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    # === ATIVO - Operações ===
    ("Dell Inspiron 15 5510","DSOPE010","Gabriel de Moraes Santos","Operações","OK","OK","OK","003.212","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 3511","DSOPE003","João Paulo Parreira","Operações","OK","OK","OK","003.202","Windows 11 PRO","Intel Core i5- 1135g7","8GB","SSD256","Ótimo","10/10/2022"),
    ("Dell Inspiron 15 5510","DSOPE009","João Victor Daleffi","Operações","OK","OK","OK","003.215","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 3530","DSGER017","Robson Bertoni","Operações","OK","OK","OK","003.944","Windows 11 PRO","Intel i5 13ª","16GB","500 SSD","Ótimo",""),
    # === ATIVO - P&D ===
    ("Dell Inspiron 15 3000 (3501)","DSPED020","Cassia Milena","P&D","OK","OK","OK","002.529","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 3530","DSPED001","Frederico Guimarães","P&D","OK","OK","OK","003.948","Windows 11 PRO","Intel i5 13ª","16GB","504 SSD","Ótimo",""),
    ("Dell Inspiron 15 3000 (3501)","DSPED021","Gabriela Bobroff","P&D","OK","OK","OK","002.528","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 5510","DSPED022","Raphael Calcanho","P&D","OK","OK","OK","003.245","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    # === ATIVO - Portaria ===
    ("Dell Inspiron 3511","DSPOR005","Portaria","Portaria","OK","OK","OK","003.203","Windows 11 PRO","Intel Core i5- 1135g7","8GB","SSD256","Ótimo","10/10/2022"),
    # === ATIVO - Produção ===
    ("Dell Inspiron 3442","DSFUN002","Funcionários Produção","Produção","OK","OK","OK","(SEM PLACA)","Windows 10 PRO","Intel Core i3 - 4005U","4GB","500GB","Regular",""),
    ("Dell Inspiron 15 3000","DSPROD022","Produção 3 - Flavio","Produção","OK","OK","OK","001.773","Windows 10 PRO","Intel Core I5 - 7200U","8GB","1TB","Ótimo","28/02/2018"),
    ("Dell Inspiron 15 3000 (3501)","DSPROD022","Produção 4 - Marcos","Produção","OK","OK","OK","002.506","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 3511","DSPROD021","Produção 6 - Alisson","Produção","OK","OK","OK","003.201","Windows 11 PRO","Intel Core i5- 1135g7","8GB","SSD256","Ótimo",""),
    ("Dell Vostro 5480","DSPROD017","Produção 7 - Jean","Produção","OK","OK","OK","001.782","Windows 10 PRO","Intel Core I7 - 5500U","8GB","500GB SSD","Bom",""),
    ("Dell Inspiron 7460","DSPROD020","Produção 9 - Sala Adervaldo","Produção","OK","OK","OK","001.753","Windows 10 PRO","Intel Core I5 - 7200U","8GB","1TB","Ótimo",""),
    # === ATIVO - Registros ===
    ("Dell Inspiron 15 3000 (3501)","DSREG005","Ana Zanuto","Registros","OK","OK","OK","002.524","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Inspiron 15 5510","DSREG006","João Rios do Carmo","Registros","OK","OK","OK","003.226","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    # === ATIVO - RH ===
    ("Dell Inspiron 3511","DSRH018","Amanda Martins","RH","OK","OK","OK","003.205","Windows 11 PRO","Intel Core i5- 1135g7","8GB","SSD256","Ótimo","10/10/2022"),
    ("Dell Inspiron 15 5510","DSRH016","José Leonardo","RH","OK","OK","OK","003.236","Windows 10 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 5510","DSRH021","Rafaela Toneto","RH","OK","OK","OK","003.243","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Dell Inspiron 15 5510","DSRH019","Rosária","RH","OK","OK","OK","003.213","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    # === ATIVO - Tec. Segurança ===
    ("Dell Inspiron 15 3000 (3501)","DSRH020","Alice Santos","Tec. Segurança","OK","OK","OK","002.482","Windows 10 PRO","Intel Core I5- 1035G1","8GB","240SSD","Ótimo","01/09/2021"),
    ("Dell Vostro 3500","DSRH023","Micael Silveira","Tec. Segurança","OK","OK","OK","002.360","Windows 10 PRO","Intel Core I5 - 1135g7","8GB","256 SSD","Ótimo","24/03/2021"),
    # === ATIVO - TI ===
    ("Dell Inspiron 3511","DSAUDIT001","Auditório","TI","OK","OK","OK","003.204","Windows 11 PRO","Intel Core i5- 1135g7","8GB","SSD256","Ótimo","10/10/2022"),
    ("Dell G15 5530","DSIT0001","Mateus Furrier","TI","OK","OK","OK","003.820","Windows 11 PRO","Intel Core I7 13650HX","16GB","1TB","Ótimo",""),
    ("Dell Inspiron 15 5510","DSTI002","Pedro Rocha","TI","OK","OK","OK","003.247","Windows 11 PRO","Intel Core i7 11390H","32GB","SSD512","Ótimo","13/10/2022"),
    ("Asus 15","SALA TI","Sala TI","TI","OK","OK","OK","001.750","Windows 10 PRO","Intel Core i3 - 3110M","4GB","500GB","Bom",""),
    ("Dell Inspiron 14 5482","DSPROD018","Server ROBOPAC","TI","OK","OK","OK","002.118","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD","Ótimo","07/12/2019"),
    ("Dell Inspiron 14 5482","","Servidor","TI","","","","002.578","Windows 10 PRO","Intel Core I7 - 8565U","8GB","256 SSD","Ótimo","07/12/2019"),
    ("Dell Inspiron 3511","","Servidor Câmeras","TI","","","","003.208","Windows 11 PRO","Intel Core i5- 1135g7","8GB","SSD256","Ótimo","10/10/2022"),
    # === SEM CLASSIFICAÇÃO ===
    ("Dell Inspiron 5448","","","","","","","","Windows 10 PRO","Intel Core I7 - 5500U","8GB","1TB","Ótimo",""),
    ("Dell (acessório)","HDD KINGSTON","","","","","","002.245","","","","","",""),
    ("Dell Inspiron 5590","KIT TECLADO","","","","","","002.250","","","","","",""),
    ("Dell Inspiron 15 5510","","","","","","","003.216","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo","13/10/2022"),
    ("Asus S400CA","","","","","","","","Windows 10 PRO","Intel Core I5 - 3317U","4GB","500GB","Bom",""),
    ("Dell Inspiron 15 5510","","","","","","","","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo",""),
    ("Dell Inspiron 15 5510","","","","","","","","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo",""),
    ("Dell Inspiron 15 5510","","","","","","","","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo",""),
    ("Dell Inspiron 15 5510","","","","","","","","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo",""),
    ("Dell Inspiron 15 5510","","","","","","","","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo",""),
    ("Dell Inspiron 15 5510","","","","","","","","Windows 11 PRO","Intel Core i7 11390H","16GB","SSD512","Ótimo",""),
    ("Dell Inspiron 5448","","","","","","","","Windows 10 PRO","Intel Core I7 - 5500U","8GB","1TB","Bom",""),
    ("Dell Inspiron 5448","","","","","","","","Windows 10 PRO","Intel Core I7 - 5500U","8GB","1TB","Bom",""),
]

# Tablet (encontrado junto com dados de Operações)
TABLETS: list[tuple[str, ...]] = [
    # (modelo, usuario, setor, placa)
    ("Tablet Redmi Pad SE","Gabriel de Moraes Santos","Operações","003.598"),
]

# Smartphones: (area, colaborador, numero, aparelho, aquisicao, placa, obs)
SMARTPHONES: list[tuple[str, ...]] = [
    ("Comercial","Fernanda","(43) 99123-6022","Samsung Galaxy S9","22/04/2025","001848",""),
    ("Comercial","Guilherme Silva","(43)99153-4579","Samsung Galaxy S24 FE","26/05/2025","003804",""),
    ("Comercial","Winderson","(43) 99170-6927","Samsung Galaxy M20","24/11/2021","002116",""),
    ("Compras","Carlos/Rafael","(43) 99108-1833","Samsung Galaxy S9","01/01/2022","001849",""),
    ("Compras","Karina Silva","(43) 99190-7010","Samsung Galaxy M31","01/01/2023","002222",""),
    ("Compras","Luiz","(43) 99170-1164","Samsung Galaxy A54","20/05/2024","003617",""),
    ("Contabilidade","Renato Sobrinho","(43) 99145-8700","Samsung Galaxy S24 FE","26/05/2025","003802",""),
    ("CQ","Leticia","","Samsung Galaxy M32","","003094","Sem informação de data de recebimento"),
    ("CQ","Mayara","(43) 99133-4022","Samsung Galaxy M32","25/03/2022","003258",""),
    ("Diretoria","Marco","(43) 99123-7599","Apple iPhone 15","20/11/2023","003545",""),
    ("Financeiro","Daniel","(43) 99123-6022","Samsung Galaxy S20 FE","03/12/2024","003094b",""),
    ("Financeiro","Michael Silva","(43) 99140-4670","Samsung Galaxy S24 FE","26/05/2025","003803",""),
    ("Logistica","Anderson","(43) 99193-0754","Samsung Galaxy M32","25/03/2022","002468",""),
    ("Logistica","Cleber","(43) 99193-6452","Samsung Galaxy M32","","003093",""),
    ("Manutenção","Alex","(43) 99968-8075","Samsung Galaxy A14","","003563",""),
    ("Meio Ambiente","Marcela","","Samsung Galaxy A56","28/11/2025","003907",""),
    ("MKT","Carol Felde","(43) 99118-7909","Apple iPhone 13","23/11/2023","003546",""),
    ("MKT","Guilherme Tissiano","(43) 99180-4190","Samsung Galaxy S9","22/04/2025","002147",""),
    ("MKT","Julia","(43) 99169-0184","Apple iPhone 14 Pro","24/10/2023","003268",""),
    ("MKT","Karina F.","(43) 99169-0184","Samsung Galaxy S20 FE","01/12/2021","002634","Placa duplicada com P&D - verificar"),
    ("Operações","João Paulo","(43) 99171-4499","Samsung Galaxy A34","02/02/2024","003584",""),
    ("P&D","Cassia Silva","(43) 99131-1517","Samsung Galaxy S20 FE","","002634b","Placa duplicada com MKT - verificar"),
    ("P&D - Externo","Fabio Peron","","Samsung Galaxy A11","30/09/2025","002338",""),
    ("Portaria","Portaria","(43) 99147-1643","Samsung Galaxy M32","09/12/2024","",""),
    ("Produção","Adervaldo","","Samsung Galaxy S9","16/05/2025","",""),
    ("Registros","João Rios","(43) 99131-9801","Samsung Galaxy A54","20/05/2024","003618",""),
    ("RH","Rafaela","(43) 99146-6765","Samsung Galaxy S9","","001846",""),
    ("Segurança do Trab.","Andresa","(43) 99163-8163","Samsung Galaxy M32","21/03/2024","003257",""),
    ("TI","Mateus","(43) 99155-8899","Samsung Galaxy S24 FE","26/05/2025","003801",""),
    ("TI","Sala TI","","Samsung Galaxy S10","","001917","Tela quebrada"),
    ("TI","Sala TI","","Samsung Galaxy S20 FE","","002601","Patrimônio alternativo: 002574"),
    ("TI","Sala TI","","Samsung Galaxy S23","","003479",""),
    ("TI","Sala TI","","Samsung Galaxy S23","","003478",""),
    ("DESCARTADO","","","Samsung Galaxy S20 FE","","",""),
    ("DESCARTADO","","","Samsung Galaxy J5","","",""),
    ("DESCARTADO","","","Samsung Galaxy A11","","",""),
]


def insert_asset(cur: "psycopg2.cursor", row: dict) -> str | None:  # type: ignore[type-arg]
    try:
        cur.execute(
            """
            INSERT INTO helpdesk.assets
              (asset_tag, asset_type, brand, model, status,
               holder_name, holder_dept, acquired_at,
               specs, compliance, notes, created_by)
            VALUES
              (%(tag)s,%(atype)s,%(brand)s,%(model)s,%(status)s,
               %(holder_name)s,%(holder_dept)s,%(acquired_at)s,
               %(specs)s::jsonb,%(compliance)s::jsonb,%(notes)s,'system_import')
            ON CONFLICT (asset_tag) DO NOTHING
            RETURNING id
            """,
            row,
        )
        result = cur.fetchone()
        return str(result[0]) if result else None
    except Exception as e:
        print(f"  ERRO {row.get('tag')} / {row.get('model')}: {e}", file=sys.stderr)
        return None


def insert_history(cur: "psycopg2.cursor", asset_id: str, name: str | None, dept: str | None) -> None:  # type: ignore[type-arg]
    cur.execute(
        """
        INSERT INTO helpdesk.asset_history
          (asset_id, action, holder_name, holder_dept, changed_by, notes)
        VALUES (%s,'created',%s,%s,'system_import','Importação inicial do inventário')
        """,
        (asset_id, name, dept),
    )


def main() -> None:
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    nb_ok = nb_skip = sm_ok = sm_skip = tb_ok = 0

    print("=== Notebooks ===")
    for row in NOTEBOOKS:
        modelo, nome_pc, usuario, setor, av, fi, tr, placa, so, proc, ram, hd, cond, aqq = row
        brand, full_model = _brand(modelo)
        status = _nb_status(usuario)
        holder_name, holder_dept = _nb_holder(usuario, setor)
        tag = _tag(placa)

        specs: dict[str, str] = {}
        problem_desc = any(kw in nome_pc.lower() for kw in ("ruim", "kit", "hdd", "teclado"))
        if nome_pc.strip() and not problem_desc:
            specs["computer_name"] = nome_pc.strip()
        if so.strip():
            specs["os_version"] = so.strip()
        if proc.strip():
            specs["processor"] = proc.strip()
        if ram.strip():
            specs["ram"] = ram.strip()
        if hd.strip():
            specs["storage"] = hd.strip()

        compliance: dict[str, bool] = {}
        if av.strip() or fi.strip() or tr.strip():
            compliance["antivirus"] = _bool(av)
            compliance["fusion_inventory"] = _bool(fi)
            compliance["responsibility_term"] = _bool(tr)

        notes_parts: list[str] = []
        if cond.strip():
            notes_parts.append(f"Condição física: {cond.strip()}")
        if nome_pc.strip() and problem_desc:
            notes_parts.append(f"Obs: {nome_pc.strip()}")
        if usuario.strip().upper() == "FURTO":
            notes_parts.append("Baixado por furto")

        atype = "other" if "acessório" in modelo.lower() else "notebook"

        payload = {
            "tag": tag, "atype": atype, "brand": brand, "model": full_model,
            "status": status, "holder_name": holder_name, "holder_dept": holder_dept,
            "acquired_at": _date(aqq),
            "specs": json.dumps(specs, ensure_ascii=False),
            "compliance": json.dumps(compliance, ensure_ascii=False),
            "notes": "\n".join(notes_parts) or None,
        }
        aid = insert_asset(cur, payload)
        if aid:
            insert_history(cur, aid, holder_name, holder_dept)
            nb_ok += 1
        else:
            nb_skip += 1

    print(f"  {nb_ok} inseridos, {nb_skip} ignorados (placa duplicada)")

    print("=== Tablets ===")
    for modelo, usuario, setor, placa in TABLETS:
        brand, full_model = _brand(modelo)
        payload = {
            "tag": _tag(placa), "atype": "tablet", "brand": brand, "model": full_model,
            "status": "active", "holder_name": usuario or None, "holder_dept": setor or None,
            "acquired_at": None,
            "specs": json.dumps({}), "compliance": json.dumps({}), "notes": None,
        }
        aid = insert_asset(cur, payload)
        if aid:
            insert_history(cur, aid, usuario or None, setor or None)
            tb_ok += 1
    print(f"  {tb_ok} inseridos")

    print("=== Smartphones ===")
    for row in SMARTPHONES:
        area, colaborador, numero, aparelho, aqq, placa, obs = row
        brand, full_model = _brand(aparelho)
        tag = _tag(placa)

        if area.strip().upper() == "DESCARTADO":
            status, holder_name, holder_dept = "retired", None, None
        elif "tela quebrada" in obs.lower():
            status = "maintenance"
            holder_name, holder_dept = colaborador.strip() or None, area.strip() or None
        else:
            status = "active"
            holder_name, holder_dept = colaborador.strip() or None, area.strip() or None

        specs: dict[str, str] = {}
        ph = _phone(numero)
        if ph:
            specs["phone_number"] = ph

        payload = {
            "tag": tag, "atype": "smartphone", "brand": brand, "model": full_model,
            "status": status, "holder_name": holder_name, "holder_dept": holder_dept,
            "acquired_at": _date(aqq),
            "specs": json.dumps(specs, ensure_ascii=False),
            "compliance": json.dumps({}),
            "notes": obs.strip() or None,
        }
        aid = insert_asset(cur, payload)
        if aid:
            insert_history(cur, aid, holder_name, holder_dept)
            sm_ok += 1
        else:
            sm_skip += 1

    print(f"  {sm_ok} inseridos, {sm_skip} ignorados (placa duplicada)")

    conn.commit()
    cur.close()
    conn.close()
    total = nb_ok + tb_ok + sm_ok
    print(f"\nTotal: {total} ativos importados ao banco.")


if __name__ == "__main__":
    main()
