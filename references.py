"""IEEE references in order of first citation. ES/EN variants; anonymised self-citations for blinded review."""

def refs(lang="es", anonymous=False):
    acc = "consultado: octubre de 2026" if lang == "es" else "accessed: Oct. 2026"
    online = "[en línea]. Disponible en:" if lang == "es" else "[Online]. Available:"
    rev = "manuscrito en evaluación" if lang == "es" else "manuscript under review"
    if anonymous:
        r14 = ("[Autor anonimizado], “Comparación de una red distribuida de IA y alimentos con un campus centralizado a gas en Canadá”, " + rev + ", 2026."
               if lang == "es" else "[Anonymised author], “Comparison of a distributed AI-and-food network with a centralised gas-fired campus in Canada”, " + rev + ", 2026.")
        r15 = ("[Autor anonimizado], “Transporte renovable en Costa Rica: eólica marina, combustibles termosolares de macroalgas y electrificación”, " + rev + ", 2026."
               if lang == "es" else "[Anonymised author], “Renewable transport in Costa Rica: offshore wind, solar-thermal seaweed fuels and electrification”, " + rev + ", 2026.")
    else:
        r14 = "J. K. Bily, “Digital Gardens versus Wonder Valley: a prospective Canadian planning comparison of AI infrastructure, seasonal food systems, recoverable heat and community outcomes, 2026–2041”, " + rev + ", 2026."
        r15 = ("J. K. Bily, C. Pahl y P. Valdés Bacallao, “Transporte renovable en Costa Rica: eólica marina, combustibles termosolares de macroalgas y electrificación”, " + rev + ", 2026."
               if lang == "es" else "J. K. Bily, C. Pahl and P. Valdés Bacallao, “Renewable transport in Costa Rica: offshore wind, solar-thermal seaweed fuels and electrification”, " + rev + ", 2026.")
    y = "y" if lang == "es" else "and"
    R = [
        f"Instituto Costarricense de Electricidad, Centro Nacional de Control de Energía, “Informe de atención de la demanda y producción de electricidad 2025”, ICE, San José, Costa Rica, 2026. {online} https://apps.grupoice.com/CenceWeb/documentos/3/3008/27/R01-PDOCSE-07%20Informe_Atenci%C3%B3n%20demanda%20y%20producci%C3%B3n_2025_v2_firmado.pdf ({acc}).",
        f"El Observador, “Costa Rica recupera su matriz eléctrica limpia con un 98,6 % de generación renovable en 2025”, 2026. {online} https://observador.cr/costa-rica-recupera-su-matriz-electrica-limpia-con-un-986-de-generacion-renovable-en-2025/ ({acc}).",
        f"The Tico Times, “Who is behind Costa Rica’s AI data centers in Limón and Bagaces?”, 27 sep. 2026. {online} https://ticotimes.net/2026/09/27/costa-rica-ai-data-centers-limon-bagaces-power-water ({acc}).",
        f"Quantum Development Inc., “Infrastructure – Quantum AI Free Zone Campus”. {online} http://quantumfz.com/infrastructure/ ({acc}).",
        f"Voz de Guanacaste, “A data center in Bagaces is setting off environmental alarms. Here’s what we know”, 2026. {online} https://vozdeguanacaste.com/en/a-data-center-in-bagaces-is-setting-off-environmental-alarms-heres-what-we-know/ ({acc}).",
        f"La República, “Guanacaste será sede de un nuevo campus de IA con su propio modelo energético renovable”, 2025. {online} https://www.larepublica.net/noticia/guanacaste-sera-sede-de-un-nuevo-campus-de-ia-con-su-propio-modelo-energetico-renovable ({acc}).",
        f"El Financiero, “¿Data center de IA en Limón? Los desafíos climáticos, hídricos y de empleo del proyecto”, 2026. {online} https://www.elfinancierocr.com/economia-y-politica/data-center-de-ia-en-limon-los-desafios-climaticos/IIVLWM3A2ZA3PIDD3WQCI4GX4M/story/ ({acc}).",
        f"FreshPlaza, “Against the mango giants: how Costa Rica carves out a niche between Peru and Mexico”, 2026. {online} https://www.freshplaza.com/north-america/article/9823475/against-the-mango-giants-how-costa-rica-carves-out-a-niche-between-peru-and-mexico/ ({acc}).",
        f"FreshPlaza, “Banana exports fall 20.7 % in Costa Rica”, 2025. {online} https://www.freshplaza.com/latin-america/article/9764007/banana-exports-fall-20-7-in-costa-rica/ ({acc}).",
        "A. M. Afanador, “El banano verde de rechazo en la producción de alcohol carburante”, Revista EIA, no. 3, pp. 51–68, 2005.",
        f"CMBroker Commodity Board, “Dried mango prices hold firm as Thai supply risk meets Vietnam harvest”, 19 abr. 2026. {online} https://commodity-board.com/dried-mango-prices-hold-firm-as-thai-supply-risk-meets-vietnam-harvest/ ({acc}).",
        f"CMBroker Commodity Board, “Banana chips prices firm as PH and VN supply stay weather exposed”, 28 ago. 2026. {online} https://commodity-board.com/banana-chips-prices-firm-as-ph-and-vn-supply-stay-weather-exposed ({acc}).",
        "Secadores Digitales de Costa Rica, “Red hidroeléctrica y fibra: 32 sitios candidatos y modelo de secadores, versión conceptual V1” (conjunto de datos y sitio web no publicado), 2026.",
        r14,
        r15,
        f"Asamblea Legislativa de Costa Rica, “Ley N.° 7200, Ley que autoriza la generación eléctrica autónoma o paralela”, 1990, reformada por la Ley N.° 7508, 1995. {online} https://aresep.go.cr/wp-content/uploads/2015/02/Ley-Generacion-Electrica-Autonoma-o-Paralela.pdf ({acc}).",
        f"Semanario Universidad, “Cifras del ICE desmienten la prisa por abrir el mercado de generación eléctrica”, 2026. {online} https://semanariouniversidad.com/pais/cifras-del-ice-desmienten-la-prisa-por-abrir-el-mercado-de-generacion-electrica/ ({acc}).",
        f"Asamblea Legislativa de Costa Rica, “Ley N.° 10086, Promoción y regulación de recursos energéticos distribuidos a partir de fuentes renovables”, 2021. {online} https://leap.unep.org/en/countries/cr/national-legislation/ley-10086-del-8-de-diciembre-del-2021-promocion-y-regulacion-de ({acc}).",
        f"Delfino, “El sol no brilla para todos: desilusiones y paradojas de la Ley 10086”, mar. 2024. {online} https://delfino.cr/2024/03/el-sol-no-brilla-para-todos-desilusiones-y-paradojas-de-la-ley-10086 ({acc}).",
        f"CR Prensa, “Asamblea Legislativa de Costa Rica archiva proyecto de reforma eléctrica del Gobierno”, 19 oct. 2026. {online} https://crprensa.com/2026/10/19/asamblea-legislativa-de-costa-rica-archiva-proyecto-de-reforma-electrica-del-gobierno/ ({acc}).",
        f"Lenovo, “ThinkSystem NVIDIA GB300 NVL72 datasheet (DS0207)”. {online} https://lenovopress.lenovo.com/ds0207 ({acc}).",
        "Information technology — Data centres key performance indicators — Part 6: Energy Reuse Factor (ERF), ISO/IEC 30134-6:2021.",
        f"The Green Grid, “ERE: a metric for measuring the benefit of reuse energy from a data center”, White Paper 29, 2010.",
        f"U.S. Department of Agriculture, Agricultural Research Service, “FoodData Central: mangos, raw; bananas, raw; plantains, raw (SR Legacy)”. {online} https://fdc.nal.usda.gov/ ({acc}).",
        "A. S. Mujumdar, Ed., Handbook of Industrial Drying, 4.ª ed. Boca Raton, FL, USA: CRC Press, 2014." if lang == "es" else "A. S. Mujumdar, Ed., Handbook of Industrial Drying, 4th ed. Boca Raton, FL, USA: CRC Press, 2014.",
        "Intergovernmental Panel on Climate Change, 2006 IPCC Guidelines for National Greenhouse Gas Inventories, vol. 2, Energy, cap. 1, cuadro 1.4. Hayama, Japón: IGES, 2006." if lang == "es" else "Intergovernmental Panel on Climate Change, 2006 IPCC Guidelines for National Greenhouse Gas Inventories, vol. 2, Energy, ch. 1, Table 1.4. Hayama, Japan: IGES, 2006.",
        f"The Register, “Nvidia’s Vera Rubin CPU, GPU roadmap charts course for hot-hot-hot 600 kW racks”, 19 mar. 2025. {online} https://www.theregister.com/2025/03/19/nvidia_charts_course_for_600kw ({acc}).",
        "H. Hersbach et al., “The ERA5 global reanalysis”, Quarterly Journal of the Royal Meteorological Society, vol. 146, no. 730, pp. 1999–2049, 2020, doi: 10.1002/qj.3803.",
        f"MarViva, “Maricultura en Costa Rica”, San José, Costa Rica, feb. 2023. {online} https://marviva.net/wp-content/uploads/2023/03/Maricultura-en-Costa-Rica-DIGITAL-Febrero-2023-final-1.pdf ({acc}).",
        "J. I. Hernández et al., “Improvement in spotted rose snapper growth and skin coloration after incorporation of shrimp head meal in diet”, Aquaculture Reports, vol. 30, art. 101599, 2023, doi: 10.1016/j.aqrep.2023.101599.",
        f"M. A. J. Nederlof, M. C. J. Verdegem, A. C. Smaal {y} H. M. Jansen, “Nutrient retention efficiencies in integrated multi-trophic aquaculture”, Reviews in Aquaculture, vol. 14, no. 3, pp. 1194–1212, 2022, doi: 10.1111/raq.12645.",
        "Information technology — Data centres key performance indicators — Part 8: Carbon usage effectiveness (CUE), ISO/IEC 30134-8:2022.",
        f"I. Kumar {y} S. Manning, “Trends in frontier AI model count: a forecast to 2028”, arXiv:2504.16138, 2025.",
        "A. Douillard et al., “DiLoCo: distributed low-communication training of language models”, arXiv:2311.08105, 2023.",
        f"NVIDIA, “NVIDIA introduces Spectrum-XGS Ethernet to connect distributed data centers into giga-scale AI super-factories”, 22 ago. 2025. {online} https://nvidianews.nvidia.com/news/nvidia-introduces-spectrum-xgs-ethernet-to-connect-distributed-data-centers-into-giga-scale-ai-super-factories ({acc}).",
        f"GBM Media (Reuters), “Costa Rica reporta su menor cosecha de café en 55 años”, 24 jun. 2026. {online} https://gbm.com/media/noticia/costa-rica-reporta-su-menor-cosecha-de-cafe-en-55-anos/ ({acc}).",
        f"J. E. Braham {y} R. Bressani, Eds., Coffee Pulp: Composition, Technology, and Utilization, IDRC-108e. Ottawa, ON, Canada: International Development Research Centre, 1979.",
        f"Portal Frutícola, “Costa Rica proyecta finalizar el 2023 con 180 millones de cajas de piña”, 19 dic. 2023. {online} https://www.portalfruticola.com/?p=548478 ({acc}).",
        "S. Rodríguez-Chacón, M. López-Herrera, R. WingChing-Jones y A. Rojas-Bourrillón, “Adición de melaza deshidratada y urea en ensilados de rastrojos de piña”, Agronomía Mesoamericana, vol. 25, no. 2, pp. 313–321, 2014." if lang == "es" else "S. Rodríguez-Chacón, M. López-Herrera, R. WingChing-Jones and A. Rojas-Bourrillón, “Adición de melaza deshidratada y urea en ensilados de rastrojos de piña”, Agronomía Mesoamericana, vol. 25, no. 2, pp. 313–321, 2014.",
        f"El Mundo CR, “Senasa prohíbe derribas en fincas piñeras para control de Stomoxys calcitrans”, 1 ago. 2017. {online} https://elmundo.cr/costa-rica/senasa-prohibe-derribas-fincas-pineras-control-stomoxis-calcitrans/ ({acc}).",
        f"Ministerio de Agricultura y Ganadería, “Pasto transvala secano, Región Chorotega 2026: costo de producción de heno”, Infoagro, 2026. {online} https://www.infoagro.go.cr/wp-content/uploads/2026/03/Pasto_transvala_secano_Chorotega_2026.pdf ({acc}).",
        f"V. Heuzé, G. Tran, H. Archimède, D. Renaudeau {y} M. Lessire, “Banana fruits”, Feedipedia, INRAE, CIRAD, AFZ {y} FAO. {online} https://www.feedipedia.org/node/683 ({acc}).",
        f"L. J. Goh, M. Y. Othman, S. Mat, H. Ruslan {y} K. Sopian, “Review of heat pump systems for drying application”, Renewable and Sustainable Energy Reviews, vol. 15, no. 9, pp. 4788–4796, 2011, doi: 10.1016/j.rser.2011.07.072.",
        f"C. O. Perera {y} M. S. Rahman, “Heat pump dehumidifier drying of food”, Trends in Food Science & Technology, vol. 8, no. 3, pp. 75–79, 1997.",
        f"Ministerio de Salud de Costa Rica, “Decreto N.° 38924-S, Reglamento para la Calidad del Agua Potable”, 2015. {online} https://leap.unep.org/en/countries/cr/national-legislation/decreto-no-38924-s-reglamento-para-la-calidad-del-agua-potable ({acc}).",
        f"A. Z. Rivero, “Impulsores de data centers de IA en Costa Rica aparecen en bases sobre paraísos fiscales”, Semanario Universidad, 7 oct. 2026. {online} https://semanariouniversidad.com/pais/impulsores-de-data-centers-de-ia-en-costa-rica-aparecen-en-bases-sobre-paraisos-fiscales/ ({acc}).",
        f"AMCompute, “GB300 cloud pricing”, 25 oct. 2026. {online} https://www.amcompute.com/gpu-cloud-prices/gb300 ({acc}).",
        f"C. Zeoli, “How much does an NVIDIA NVL72 cost?”, Wing VC, ago. 2026. {online} https://www.wing.vc/content/how-much-does-an-nvidia-nvl72-cost ({acc}).",
        f"AMCompute, “GB300 NVL72 appraisal”, oct. 2026. {online} https://www.amcompute.com/appraisals/gb300-nvl72 ({acc}).",
        f"La Nación, “De 4 a 2,8 personas por casa: así se redujo el hogar”, 2023. {online} https://www.nacion.com/el-pais/de-4-a-28-personas-por-casa-asi-se-redujo-el-hogar/QYYSDIFYQZFDZCGQQZIQYGXLGA/story/ ({acc}).",
        f"Instituto Nacional de Estadística y Censos, “Estimación de la población de 2022 por distrito”, consultado mediante Telencuestas. {online} https://telencuestas.com/censos-de-poblacion/costa-rica/2022 ({acc}).",
        f"Delfino, “Generación eléctrica renovable cayó en 2024 por debajo del 90 % por primera vez en 10 años”, feb. 2025. {online} https://delfino.cr/2025/02/generacion-electrica-renovable-cayo-en-2024-por-debajo-del-90-por-primera-vez-en-10-anos ({acc}).",
        f"S. Jaghouar et al., “INTELLECT-1 technical report”, arXiv:2412.01152, 2024.",
        f"Portal Frutícola, “Plantaciones de piña en Costa Rica crecen un 16 % interanual” (datos MOCUPP, Laboratorio PRIAS, CENAT-CONARE), 15 ene. 2019. {online} https://www.portalfruticola.com/?p=258895 ({acc}).",
        f"Instituto Costarricense de Electricidad, Centro Nacional de Control de Energía, “Informe de generación renovable 2024”, ICE, San José, Costa Rica, 2025. {online} https://apps.grupoice.com/CenceWeb/documentos/3/3008/23/INFORME%20GENERACION%20RENOVABLE%202024.pdf ({acc}).",
        f"I. Staffell {y} S. Pfenninger, “Using bias-corrected reanalysis to simulate current and future wind power output”, Energy, vol. 114, pp. 1224–1239, 2016, doi: 10.1016/j.energy.2016.08.068.",
        f"D. A. Lavers, A. Simmons, F. Vamborg {y} M. J. Rodwell, “An evaluation of ERA5 precipitation for climate monitoring”, Quarterly Journal of the Royal Meteorological Society, vol. 148, no. 748, pp. 3152–3165, 2022, doi: 10.1002/qj.4351.",
        f"Decreto Ejecutivo N.° 41779-H, Reglamento de la Ley del Impuesto sobre el Valor Agregado, San José, Costa Rica, 2019. {online} https://www2.uned.ac.cr/ejecutiva/direccionfinanciera/images/direccion-financiera/leyes_decretos/reglamento_iva.pdf ({acc}).",
        f"MarViva, “La comercialización de camarón marino de la costa pacífica de Costa Rica”, San José, Costa Rica, 2023. {online} https://marviva.net/wp-content/uploads/2023/11/La-comercializacion-de-camaron-marino-de-la-costa-pacifica-de-Costa-Rica.pdf ({acc}).",
        f"Ministério da Agricultura e Pecuária do Brasil, Adidância Agrícola na Costa Rica, “Costa Rica: um olhar sobre o mercado de mel de abelha na Costa Rica”, s. f. {online} https://www.gov.br/agricultura/pt-br/assuntos/relacoes-internacionais/adidos-agricolas/costa-rica/COSTARICAUMOLHARSOBREOMERCADODEMELDEABELHANACOSTARICA.pdf ({acc}).",
        f"El Mundo CR, “Apicultores de Costa Rica rechazan el CPTPP: defendemos nuestra supervivencia, no un capricho comercial”, 20 oct. 2026. {online} https://elmundo.cr/costa-rica/apicultores-de-costa-rica-rechazan-el-cptpp-defendemos-nuestra-supervivencia-no-un-capricho-comercial/ ({acc}).",
        f"P. Chorbiński et al., “The impact of buckwheat and paulownia (Paulownia elongata × P. fortunei) intercropping on beekeeping value and buckwheat yield”, Scientific Reports, vol. 14, art. 21490, 2024, doi: 10.1038/s41598-024-72493-x.",
        f"The Western Producer, “U.S. bee research gives varroa mites the cold shoulder”, 8 jul. 2021. {online} https://www.producer.com/news/u-s-bee-research-gives-varroa-mites-the-cold-shoulder/ ({acc}).",
        f"B. B. Saha, A. Akisawa {y} T. Kashiwagi, “Solar/waste heat driven two-stage adsorption chiller: the prototype”, Renewable Energy, vol. 23, no. 1, pp. 93–101, 2001, doi: 10.1016/S0960-1481(00)00107-5.",
        f"Gemini Team, “Gemini: a family of highly capable multimodal models”, arXiv:2312.11805, 2023.",
        f"NVIDIA, “How to connect distributed data centers into large AI factories with scale-across networking”, NVIDIA Technical Blog, 2025. {online} https://developer.nvidia.com/blog/how-to-connect-distributed-data-centers-into-large-ai-factories-with-scale-across-networking/ ({acc}).",
    ]
    if lang == "en":
        R = [r.replace(" 8 jul. 2021", " 8 Jul. 2021").replace(", s. f.", ", n.d.").replace(" 20 oct. 2026", " 20 Oct. 2026").replace("Decreto Ejecutivo N.° 41779-H, Reglamento de la Ley del Impuesto sobre el Valor Agregado", "Executive Decree No. 41779-H, Regulation of the Value Added Tax Law").replace(" ene. 2019", " Jan. 2019").replace(" sep. 2026", " Sep. 2026").replace(" abr. 2026", " Apr. 2026").replace(" ago. 2026", " Aug. 2026").replace(" ago. 2025", " Aug. 2025").replace(" mar. 2024", " Mar. 2024").replace(" mar. 2025", " Mar. 2025").replace(" feb. 2023", " Feb. 2023").replace(" jun. 2026", " Jun. 2026").replace(" dic. 2023", " Dec. 2023").replace(" ago. 2017", " Aug. 2017").replace(", feb. 2025", ", Feb. 2025").replace(" oct. 2026", " Oct. 2026").replace(", ago. 2026", ", Aug. 2026").replace("consultado mediante Telencuestas", "accessed via Telencuestas").replace("Estimación de la población de 2022 por distrito", "2022 population estimates by district").replace("Plantaciones de piña en Costa Rica crecen un 16 % interanual” (datos MOCUPP", "Pineapple plantations in Costa Rica grow 16% year on year” (MOCUPP data").replace("Informe de generación renovable 2024", "Renewable generation report 2024")
             .replace("Decreto N.° 38924-S, Reglamento para la Calidad del Agua Potable", "Decree No. 38924-S, Regulation on drinking-water quality")
             .replace("costo de producción de heno", "hay production cost")
             .replace("(conjunto de datos y sitio web no publicado)", "(unpublished dataset and website)").replace(", reformada por la Ley N.° 7508, 1995", ", amended by Law No. 7508, 1995")
             for r in R]
    return [f"[{i + 1}] {r}" for i, r in enumerate(R)]
