import duckdb, pathlib

data = """ADT\tJohn Nárvaez\t107596\tD
ADT\tJuan Valencia\t805423\tGK
ADT\tJoao Rojas\t52068\tF
ADT\tRonny Biojó\t965873\tD
ADT\tLuis Pérez\t1098312\tM
ADT\tLuis Gómez\t1022095\tM
ADT\tJonatan Bauman\t894452\tF
Alianza Atlético\tJosé Villegas\t1018422\tD
Alianza Atlético\tFranco Coronel\t974679\tF
Alianza Atlético\tGermán Díaz\t1116337\tM
Alianza Atlético\tValentín Robaldo\t1800727\tF
Alianza Atlético\tAriel Muñoz\t939946\tM
Alianza Atlético\tRomán Suárez\t1197978\tD
Alianza Atlético\tCristian Penilla\t220439\tM
Alianza Lima\tAlan Cantero\t1084961\tM
Alianza Lima\tEryc Castillo\t338957\tF
Alianza Lima\tFernando Gaibor\t106461\tM
Alianza Lima\tFederico Girotti\t966164\tF
Alianza Lima\tLuis Advíncula\t149850\tD
Alianza Lima\tGuillermo Viscarra\t331437\tGK
Alianza Lima\tMateo Antoni\t1116589\tD
Atlético Grau\tEmiliano Franco\t830888\tM
Atlético Grau\tRodrigo Tapia\t830660\tD
Atlético Grau\tDiego Barreto\t888377\tM
Atlético Grau\tLucas Acevedo\t384260\tD
Atlético Grau\tIgnacio Tapia\t845431\tD
Atlético Grau\tIsaac Camargo\t1173448\tF
Cienciano\tKevin Becerra\t931653\tD
Cienciano\tCarlos Garcés\t906002\tF
Cienciano\tGonzalo Falcón\t805312\tGK
Cienciano\tClaudio Núñez\t923677\tD
Cienciano\tJuan Romagnoli\t898631\tM
Cienciano\tCristian Souza\t924895\tM
Cienciano\tNeri Bandiera\t830746\tF
Comerciantes Unidos\tMatías Sen\t960220\tF
Comerciantes Unidos\tDaniel Lino\t1184194\tD
Comerciantes Unidos\tWilter Ayoví\t826832\tM
Comerciantes Unidos\tÁlvaro Villete\t876939\tGK
Comerciantes Unidos\tAgustín Rodríguez\t1468047\tM
Comerciantes Unidos\tJuan Rodríguez\t1654120\tD
Comerciantes Unidos\tMaximiliano Pérez\t873619\tF
Cusco FC\tFacundo Callejo\t325609\tF
Cusco FC\tGabriel Carabajal\t830742\tM
Cusco FC\tIván Colman\t829029\tM
Cusco FC\tLucas Colitto\t586956\tM
Cusco FC\tNicolás Silva\t830880\tM
Cusco FC\tJuan Tévez\t923196\tF
Deportivo Garcilaso\tFrancisco Arancibia\t385894\tF
Deportivo Garcilaso\tAgustín Gómez\t873645\tD
Deportivo Garcilaso\tAgustín González\t924762\tM
Deportivo Garcilaso\tAgustín Graneros\t1096363\tF
Deportivo Garcilaso\tCarlos Ramos\t1009256\tM
Deportivo Garcilaso\tJosé Sinisterra\t914211\tF
Deportivo Moquegua\tNicolás Chávez\t927088\tM
Deportivo Moquegua\tBryan Angulo\t588584\tF
Deportivo Moquegua\tJeferson Collazos\t883388\tF
Deportivo Moquegua\tCristian Enciso\t339929\tD
Deportivo Moquegua\tÉdgar Lastre\t1018573\tF
Deportivo Moquegua\tYorman Zapata\t994724\tF
FBC Melgar\tPablo Erustes\t1466382\tF
FBC Melgar\tLautaro Guzmán\t960016\tM
FBC Melgar\tJesús Alcántar\t1046624\tD
FBC Melgar\tFranco Zanelatto\t973650\tM
FBC Melgar\tJeriel de Santis\t944825\tF
FBC Melgar\tJavier Salas\t755394\tM
FC Cajamarca\tMatías Almirón\t1526674\tD
FC Cajamarca\tAlexis Rodas\t932098\tD
FC Cajamarca\tJonathan Betancourt\t356340\tM
FC Cajamarca\tTomás Andrade\t814017\tM
FC Cajamarca\tArley Rodríguez\t832001\tM
Juan Pablo II College\tMartín Alaníz\t339123\tM
Juan Pablo II College\tCristian García\t943177\tM
Juan Pablo II College\tAdán Henricks\t1522872\tF
Juan Pablo II College\tIago Iriarte\t1119882\tD
Juan Pablo II College\tMatías Vega\t789265\tGK
Juan Pablo II College\tMaximiliano Juambeltz\t1177407\tF
Los Chankas\tCarlos Pimienta\t1121487\tD
Los Chankas\tHéctor González\t991108\tD
Los Chankas\tFranco Torres\t1098306\tM
Los Chankas\tAbdiel Ayarza\t976302\tM
Los Chankas\tJarlin Quintero\t805451\tF
Los Chankas\tMarlon Torres\t972824\tF
Los Chankas\tJuan Ospina\t1088761\tF
Sport Boys\tFederico Illanes\t789416\tM
Sport Boys\tNicolás Da Campo\t777249\tM
Sport Boys\tRenzo Alfani\t862216\tD
Sport Boys\tLuciano Nequecaur\t340529\tF
Sport Boys\tJuan Torres\t1462908\tM
Sport Huancayo\tYonatan Murillo\t1100345\tD
Sport Huancayo\tJavier Sanguinetti\t351398\tF
Sport Huancayo\tNahuel Luján\t557108\tM
Sport Huancayo\tFranco Caballero\t788039\tF
Sporting Cristal\tGustavo Cazonatti\t892073\tM
Sporting Cristal\tSantiago González\t937859\tM
Sporting Cristal\tFelipe Vizeu\t839635\tF
Sporting Cristal\tGabriel Santana\t243459\tM
Sporting Cristal\tJuan Cruz González\t892451\tD
Sporting Cristal\tCristiano da Silva\t886239\tD
Universitario\tJosé Carabalí\t1017480\tD
Universitario\tCaín Fara\t971200\tD
Universitario\tSekou Gassama\t796088\tF
Universitario\tHéctor Fértoli\t831608\tM
Universitario\tLisandro Alzugaray\t897059\tF
Universitario\tMiguel Silveira\t984613\tM
UTC\tMarlon de Jesús\t143886\tF
UTC\tAdolfo Muñoz\t869785\tM
UTC\tDavid Camacho\t879886\tM
UTC\tLuis Arce\t975708\tM
UTC\tBruno Duarte\t874645\tD
UTC\tArquímedes Figuera\t123245\tM"""

team_ids = {
    'ADT': 335557,
    'Alianza Atlético': 2307,
    'Alianza Lima': 2311,
    'Atlético Grau': 282538,
    'Cienciano': 2301,
    'Comerciantes Unidos': 213609,
    'Cusco FC': 63760,
    'Deportivo Garcilaso': 458584,
    'Deportivo Moquegua': 492848,
    'FBC Melgar': 2308,
    'FC Cajamarca': 1082002,
    'Juan Pablo II College': 511206,
    'Los Chankas': 252254,
    'Sport Boys': 2312,
    'Sport Huancayo': 33895,
    'Sporting Cristal': 2302,
    'Universitario': 2305,
    'UTC': 87854,
}

particles = {'de','del','la','las','los','da','do','dos','das','di','van','von'}

def short_name(full):
    parts = [p for p in full.strip().split() if p]
    if not parts:
        return ''
    first = parts[0]
    last_parts = [parts[-1]]
    i = len(parts) - 2
    while i >= 0 and parts[i].casefold() in particles:
        last_parts.insert(0, parts[i])
        i -= 1
    return f"{first[0].upper()}. {' '.join(last_parts)}"

lines = []
for line in data.splitlines():
    team, name, pid, pos = line.split('\t')
    tid = team_ids.get(team)
    sname = short_name(name)
    lines.append(f"{pid}, {name}, {sname}, {pos}, {tid}, 0, 0, 0, 0, 0, 0")

print('\n'.join(lines))
