#let final-dir = "../part4_evaluation/reports/final/"
#let tables = final-dir + "tables/"
#let selection = json(final-dir + "model_selection.json")
#let manifest = json(final-dir + "manifest.json")
#let mvo = "Mean-Variance Optimization"
#let bl = "Black-Litterman"
#let gmv = "Global Minimum Variance"
#let maxdiv = "Maximum Diversification"
#let rp = "Risk Parity"
#let benchmark = "1/N"
#let models = (mvo, gmv, maxdiv, rp, bl, benchmark)
#let names = (
  "Mean-Variance Optimization": "Mean–variance",
  "Global Minimum Variance": "GMV",
  "Maximum Diversification": "Max. diversification",
  "Risk Parity": "Risk parity",
  "Black-Litterman": "Black–Litterman",
  "1/N": "1/N",
)
#let team = (
  ("Part 1", "Return model", "Name and contribution pending"),
  ("Part 2", "Risk model", "Name and contribution pending"),
  ("Part 3", "Portfolio construction", "Name and contribution pending"),
  ("Part 4", "Performance evaluation", "Name and contribution pending"),
)
#let records(path) = {
  let rows = csv(tables + path + ".csv")
  rows.slice(1).map(row => {
    let result = (:)
    for (i, key) in rows.first().enumerate() {
      result.insert(key, row.at(i))
    }
    result
  })
}
#let find(rows, key, name) = rows.find(row => row.at(key) == name)
#let num(value, digits: 3) = str(calc.round(float(value), digits: digits))
#let pct(value, digits: 1) = num(float(value) * 100, digits: digits) + "%"
#let pp(value, digits: 1) = num(float(value) * 100, digits: digits) + " pp"
#let score(value) = num(value, digits: 3)
#let pvalue(value) = if float(value) < .001 { "<0.001" } else { score(value) }
#let metrics = records("performance_summary")
#let model-row(name) = find(metrics, "", name)
#let stat(row, key) = float(row.at(key))
#let performance-rows = models.map(model => {
  let row = model-row(model)
  (names.at(model), pct(row.at("Annualized return")), pct(row.at("Annualized volatility")),
   score(row.at("Sharpe ratio")), pct(row.at("Maximum drawdown")))
})
#let risk = records("risk_calibration")
#let ret = records("return_forecasts")
#let risk-rows = ("Sample", "Ledoit–Wolf", "A", "B").map(method => {
  let row = risk.find(row => row.method == method and row.model == benchmark)
  (method, pct(row.predicted_vol), pct(row.realized_gross_vol), score(row.qlike),
   pvalue(row.mz_joint_p), pvalue(row.bias_p), pvalue(row.ljung_box_p))
})
#let return-rows = ("historical", "fm", "extended").map(method => {
  let row = find(ret, "", method)
  let oos = records("forecast_portfolios").find(row => row.forecast == method and row.model == mvo)
  (method, score(row.mean_rank_ic), score(row.icir), score(row.high_coverage_rank_ic),
   pct(oos.at("Annualized return")), pct(oos.at("Annualized volatility")),
   score(oos.at("Sharpe ratio")), pct(oos.at("Maximum drawdown")))
})
#let grid-table(headers, widths, rows) = table(
  columns: widths,
  align: (x, y) => if x == 0 { left } else { right },
  inset: (x: 7pt, y: 6pt),
  fill: (x, y) => if y == 0 { rgb("#e7f0f3") } else if calc.even(y) { rgb("#f5f8fa") },
  stroke: (x: none, y: 0.45pt + rgb("#d6e0e6")),
  table.header(..headers.map(heading => strong(heading))),
  ..rows.flatten(),
)
