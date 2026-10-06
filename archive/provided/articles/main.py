from graphviz import Digraph

dot = Digraph(
    name="reoptimizestep",
    format="png",
    graph_attr={
        "rankdir": "TB",
        "fontname": "Times New Roman",
        "fontsize": "12",
    },
    node_attr={
        "fontname": "Times New Roman",
        "fontsize": "12",
        "shape": "rectangle",
    },
    edge_attr={
        "fontname": "Times New Roman",
        "fontsize": "11",
    },
)

# --- Узлы ---

dot.node("start", "Начало", shape="oval")

dot.node(
    "input",
    "Ввод:\n"
    "G(t), C(t), X(t−1), X_start,\n"
    "E_crit, λ, max_iters, tol",
    shape="parallelogram",
)

dot.node("x_init", "X_curr ← X_start")
dot.node("f_init", "F_curr ← F_dynamic(C(t), X(t−1), X_curr)")
dot.node("init_vars", "iter ← 0\nimproved_any ← True")

dot.node(
    "while_cond",
    "(improved_any == True)\n∧ (iter < max_iters) ?",
    shape="diamond",
)

dot.node("iter_step", "improved_any ← False\niter ← iter + 1")

dot.node(
    "for_e",
    "Для каждого e ∈ E_crit",
    shape="doubleoctagon",
)

dot.node("try_flip", "X_trial ← trysingleedgeflip(e, X_curr)")

dot.node(
    "x_diff",
    "X_trial ≠ X_curr ?",
    shape="diamond",
)

dot.node(
    "f_new",
    "F_new ← F_dynamic(C(t), X(t−1), X_trial)",
)

dot.node(
    "f_better",
    "F_new < F_curr − tol ?",
    shape="diamond",
)

dot.node(
    "accept",
    "X_curr ← X_trial\n"
    "F_curr ← F_new\n"
    "improved_any ← True",
)

dot.node(
    "phi",
    "Φ ← countchangededges(X(t−1), X_curr)",
)

dot.node(
    "delta_f",
    "F_prev ← F_dynamic(C(t), X(t−1), X(t−1))\n"
    "ΔF ← F_curr − F_prev",
)

dot.node(
    "output",
    "Вывод:\n"
    "X(t) = X_curr\n"
    "F_dynamic = F_curr\n"
    "Φ\n"
    "ΔF\n"
    "iter",
    shape="parallelogram",
)

dot.node("end", "Конец", shape="oval")

# --- Рёбра ---

dot.edge("start", "input")
dot.edge("input", "x_init")
dot.edge("x_init", "f_init")
dot.edge("f_init", "init_vars")
dot.edge("init_vars", "while_cond")

dot.edge("while_cond", "iter_step", label="да")
dot.edge("iter_step", "for_e")
dot.edge("for_e", "try_flip")
dot.edge("try_flip", "x_diff")

dot.edge("x_diff", "for_e", label="нет")
dot.edge("x_diff", "f_new", label="да")

dot.edge("f_new", "f_better")
dot.edge("f_better", "for_e", label="нет")
dot.edge("f_better", "accept", label="да")

dot.edge("accept", "for_e")

dot.edge("while_cond", "phi", label="нет")
dot.edge("phi", "delta_f")
dot.edge("delta_f", "output")
dot.edge("output", "end")

# --- Генерация файла ---

dot.render("reoptimizestep_flowchart", cleanup=True)
