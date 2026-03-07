CATEGORY_RULES: dict[str, list[str]] = {
    "Hortifruti": ["banana", "maçã", "maca", "tomate", "alface", "batata", "cebola"],
    "Proteínas": ["frango", "carne", "patinho", "peixe", "linguiça", "ovo"],
    "Laticínios": ["leite", "iogurte", "queijo", "manteiga", "requeijão"],
    "Mercearia": ["arroz", "feijão", "macarrão", "farinha", "açúcar", "acucar", "óleo", "oleo"],
    "Padaria & snacks": ["pão", "pao", "biscoito", "salgadinho", "bolo", "torrada"],
    "Bebidas": ["suco", "refrigerante", "água", "agua", "cerveja", "vinho", "café", "cafe"],
    "Congelados & prontos": ["congelado", "lasanha", "pizza", "nuggets"],
    "Limpeza": ["detergente", "sabão", "sabao", "amaciante", "desinfetante", "água sanitária", "agua sanitaria"],
    "Higiene pessoal": ["shampoo", "sabonete", "creme dental", "desodorante", "absorvente"],
    "Bebê": ["fralda", "lenço umedecido", "lenco umedecido", "fórmula", "formula"],
    "Pet": ["ração", "racao", "petisco", "areia", "gato", "cachorro"],
    "Farmácia – medicamentos": ["dipirona", "paracetamol", "ibuprofeno", "medicamento", "xarope"],
    "Farmácia – cuidados": ["protetor", "vitamina", "curativo", "álcool", "alcool", "pomada"],
}


def suggest_category(description: str) -> tuple[str, str | None]:
    desc = description.lower()
    for category, keywords in CATEGORY_RULES.items():
        if any(keyword in desc for keyword in keywords):
            return category, None
    return "Outros", None
