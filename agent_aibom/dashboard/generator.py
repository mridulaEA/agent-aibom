"""Generate a self-contained interactive HTML dashboard from a BOM."""

from __future__ import annotations

import json
from pathlib import Path

from agent_aibom.core.models import AgenticBOM, RiskSeverity
from agent_aibom.graph import DelegationGraph, GraphVisualizer, PermissionGraph


def generate_dashboard(bom: AgenticBOM, output_path: Path) -> Path:
    """Generate a single-file HTML dashboard and write it to output_path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build graph data
    pg = PermissionGraph(bom)
    dg = DelegationGraph(bom)
    perm_d3 = GraphVisualizer.to_d3_json(pg.to_networkx())
    deleg_d3 = GraphVisualizer.to_d3_json(dg.to_networkx())

    # Build agent table data
    agents_data = []
    for a in sorted(bom.agents, key=lambda x: x.name):
        agents_data.append({
            "name": a.name,
            "framework": a.framework.value,
            "tools": len(a.tools),
            "external_tools": len(a.external_tools),
            "permissions": len(a.permissions),
            "delegations": len(a.delegations),
            "owner": a.owner or "",
            "source_file": a.source_file or "",
            "tags": ", ".join(a.tags),
        })

    # Build risk data
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    if bom.risk_score:
        for sev, count in bom.risk_score.findings_count.items():
            severity_counts[sev.value] = count

    findings_data = []
    for f in bom.risk_findings:
        findings_data.append({
            "agent": f.agent_name,
            "category": f.category.value,
            "severity": f.severity.value,
            "title": f.title,
            "source": f.source.value,
            "confidence": f.confidence,
        })

    risk_grade = bom.risk_score.grade if bom.risk_score else "N/A"
    risk_overall = bom.risk_score.overall if bom.risk_score else 0

    summary = {
        "agent_count": len(bom.agents),
        "tool_count": sum(len(a.tools) for a in bom.agents),
        "delegation_count": len(bom.delegations),
        "finding_count": len(bom.risk_findings),
        "risk_grade": risk_grade,
        "risk_overall": risk_overall,
        "repository": bom.metadata.repository or "",
        "generated_at": bom.metadata.generated_at.isoformat() if bom.metadata.generated_at else "",
    }

    html = _build_html(
        summary=summary,
        agents_json=json.dumps(agents_data),
        findings_json=json.dumps(findings_data),
        severity_json=json.dumps(severity_counts),
        perm_graph_json=perm_d3,
        deleg_graph_json=deleg_d3,
    )

    output_path.write_text(html)
    return output_path


def _build_html(
    summary: dict,
    agents_json: str,
    findings_json: str,
    severity_json: str,
    perm_graph_json: str,
    deleg_graph_json: str,
) -> str:
    grade_color = {
        "A": "#22c55e", "B": "#3b82f6", "C": "#eab308", "D": "#f97316", "F": "#ef4444",
    }.get(summary["risk_grade"], "#6b7280")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent AIBOM Dashboard</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
:root {{
  --bg: #0f172a; --surface: #1e293b; --surface2: #334155;
  --text: #f1f5f9; --text2: #94a3b8; --accent: #3b82f6;
  --critical: #ef4444; --high: #f97316; --medium: #eab308; --low: #22c55e; --info: #6b7280;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); }}
.header {{ background: var(--surface); padding: 20px 32px; border-bottom: 1px solid var(--surface2); display: flex; justify-content: space-between; align-items: center; }}
.header h1 {{ font-size: 20px; font-weight: 600; }}
.header .meta {{ color: var(--text2); font-size: 13px; }}
.stats {{ display: flex; gap: 16px; padding: 20px 32px; }}
.stat {{ background: var(--surface); border-radius: 8px; padding: 16px 20px; flex: 1; text-align: center; }}
.stat .value {{ font-size: 28px; font-weight: 700; }}
.stat .label {{ font-size: 12px; color: var(--text2); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }}
.grade {{ color: {grade_color}; }}
.tabs {{ display: flex; gap: 0; padding: 0 32px; border-bottom: 1px solid var(--surface2); background: var(--surface); }}
.tab {{ padding: 12px 20px; cursor: pointer; color: var(--text2); font-size: 14px; border-bottom: 2px solid transparent; transition: all 0.2s; }}
.tab:hover {{ color: var(--text); }}
.tab.active {{ color: var(--accent); border-bottom-color: var(--accent); }}
.content {{ padding: 24px 32px; }}
.panel {{ display: none; }}
.panel.active {{ display: block; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; padding: 10px 12px; background: var(--surface); color: var(--text2); font-weight: 500; position: sticky; top: 0; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; }}
td {{ padding: 8px 12px; border-bottom: 1px solid var(--surface2); }}
tr:hover td {{ background: var(--surface); }}
.severity {{ padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; }}
.severity.critical {{ background: rgba(239,68,68,0.2); color: var(--critical); }}
.severity.high {{ background: rgba(249,115,22,0.2); color: var(--high); }}
.severity.medium {{ background: rgba(234,179,8,0.2); color: var(--medium); }}
.severity.low {{ background: rgba(34,197,94,0.2); color: var(--low); }}
.severity.info {{ background: rgba(107,114,128,0.2); color: var(--info); }}
.search {{ padding: 8px 14px; background: var(--surface); border: 1px solid var(--surface2); border-radius: 6px; color: var(--text); font-size: 14px; margin-bottom: 16px; width: 300px; }}
.search:focus {{ outline: none; border-color: var(--accent); }}
.table-wrap {{ max-height: 600px; overflow-y: auto; border-radius: 8px; border: 1px solid var(--surface2); }}
svg {{ width: 100%; border-radius: 8px; border: 1px solid var(--surface2); background: var(--surface); }}
.chart-container {{ display: flex; gap: 24px; }}
.chart-box {{ flex: 1; }}
.node-agent {{ fill: var(--accent); }}
.node-tool {{ fill: var(--medium); }}
.node-resource {{ fill: var(--high); }}
.node-system {{ fill: var(--critical); }}
.link {{ stroke: var(--surface2); stroke-opacity: 0.6; }}
text.node-label {{ fill: var(--text); font-size: 10px; pointer-events: none; }}
.tooltip {{ position: absolute; background: var(--surface); border: 1px solid var(--surface2); padding: 8px 12px; border-radius: 6px; font-size: 12px; pointer-events: none; z-index: 100; }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>Agent AIBOM Dashboard</h1>
    <div class="meta">{summary["repository"]} &middot; {summary["generated_at"][:19]}</div>
  </div>
</div>

<div class="stats">
  <div class="stat"><div class="value grade">{summary["risk_grade"]}</div><div class="label">Risk Grade</div></div>
  <div class="stat"><div class="value">{summary["risk_overall"]}</div><div class="label">Score / 10</div></div>
  <div class="stat"><div class="value">{summary["agent_count"]}</div><div class="label">Agents</div></div>
  <div class="stat"><div class="value">{summary["tool_count"]}</div><div class="label">Tools</div></div>
  <div class="stat"><div class="value">{summary["delegation_count"]}</div><div class="label">Delegations</div></div>
  <div class="stat"><div class="value">{summary["finding_count"]}</div><div class="label">Findings</div></div>
</div>

<div class="tabs">
  <div class="tab active" onclick="showTab('inventory')">Agent Inventory</div>
  <div class="tab" onclick="showTab('risk')">Risk Findings</div>
  <div class="tab" onclick="showTab('permissions')">Permission Graph</div>
  <div class="tab" onclick="showTab('delegations')">Delegation Graph</div>
  <div class="tab" onclick="showTab('severity')">Severity Breakdown</div>
</div>

<div class="content">

<!-- Agent Inventory -->
<div class="panel active" id="panel-inventory">
<input class="search" type="text" placeholder="Search agents..." oninput="filterTable(this.value, 'agent-table')">
<div class="table-wrap">
<table id="agent-table">
<thead><tr><th>Name</th><th>Framework</th><th>Tools</th><th>External</th><th>Permissions</th><th>Delegations</th><th>Owner</th><th>Source</th></tr></thead>
<tbody id="agent-tbody"></tbody>
</table>
</div>
</div>

<!-- Risk Findings -->
<div class="panel" id="panel-risk">
<input class="search" type="text" placeholder="Search findings..." oninput="filterTable(this.value, 'risk-table')">
<div class="table-wrap">
<table id="risk-table">
<thead><tr><th>Severity</th><th>Agent</th><th>Category</th><th>Title</th><th>Source</th><th>Confidence</th></tr></thead>
<tbody id="risk-tbody"></tbody>
</table>
</div>
</div>

<!-- Permission Graph -->
<div class="panel" id="panel-permissions">
<svg id="perm-svg" height="600"></svg>
</div>

<!-- Delegation Graph -->
<div class="panel" id="panel-delegations">
<svg id="deleg-svg" height="600"></svg>
</div>

<!-- Severity Breakdown -->
<div class="panel" id="panel-severity">
<div class="chart-container">
  <div class="chart-box"><svg id="donut-svg" width="400" height="400"></svg></div>
  <div class="chart-box"><svg id="bar-svg" width="500" height="400"></svg></div>
</div>
</div>

</div>

<script>
const agents = {agents_json};
const findings = {findings_json};
const severityCounts = {severity_json};
const permGraph = {perm_graph_json};
const delegGraph = {deleg_graph_json};

// --- Tabs ---
function showTab(name) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  event.target.classList.add('active');
  if (name === 'permissions' && !window._permDrawn) {{ drawGraph(permGraph, '#perm-svg'); window._permDrawn = true; }}
  if (name === 'delegations' && !window._delegDrawn) {{ drawGraph(delegGraph, '#deleg-svg'); window._delegDrawn = true; }}
  if (name === 'severity' && !window._sevDrawn) {{ drawDonut(); drawBar(); window._sevDrawn = true; }}
}}

// --- Agent Table ---
const atb = document.getElementById('agent-tbody');
agents.forEach(a => {{
  const tr = document.createElement('tr');
  tr.innerHTML = `<td>${{a.name}}</td><td>${{a.framework}}</td><td>${{a.tools}}</td><td>${{a.external_tools}}</td><td>${{a.permissions}}</td><td>${{a.delegations}}</td><td>${{a.owner}}</td><td style="color:var(--text2);font-size:11px">${{a.source_file}}</td>`;
  atb.appendChild(tr);
}});

// --- Risk Table ---
const rtb = document.getElementById('risk-tbody');
findings.forEach(f => {{
  const tr = document.createElement('tr');
  tr.innerHTML = `<td><span class="severity ${{f.severity}}">${{f.severity}}</span></td><td>${{f.agent}}</td><td>${{f.category}}</td><td>${{f.title}}</td><td>${{f.source}}</td><td>${{(f.confidence*100).toFixed(0)}}%</td>`;
  rtb.appendChild(tr);
}});

// --- Search ---
function filterTable(q, tableId) {{
  const rows = document.querySelectorAll('#' + tableId + ' tbody tr');
  const lq = q.toLowerCase();
  rows.forEach(r => {{ r.style.display = r.textContent.toLowerCase().includes(lq) ? '' : 'none'; }});
}}

// --- Force Graph ---
function drawGraph(data, svgId) {{
  const svg = d3.select(svgId);
  const width = svg.node().getBoundingClientRect().width;
  const height = +svg.attr('height');
  svg.selectAll('*').remove();

  const g = svg.append('g');
  svg.call(d3.zoom().on('zoom', (e) => g.attr('transform', e.transform)));

  const colorMap = {{ agent: '#3b82f6', tool: '#eab308', resource: '#f97316', system: '#ef4444' }};

  const simulation = d3.forceSimulation(data.nodes)
    .force('link', d3.forceLink(data.links).distance(60))
    .force('charge', d3.forceManyBody().strength(-120))
    .force('center', d3.forceCenter(width/2, height/2))
    .force('collision', d3.forceCollide(20));

  const link = g.selectAll('.link').data(data.links).join('line').attr('class', 'link').attr('stroke-width', 1);

  const node = g.selectAll('.node').data(data.nodes).join('g').attr('class', 'node')
    .call(d3.drag().on('start', (e,d) => {{ if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }})
      .on('drag', (e,d) => {{ d.fx = e.x; d.fy = e.y; }})
      .on('end', (e,d) => {{ if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }}));

  node.append('circle').attr('r', d => d.kind === 'agent' ? 8 : 5).attr('fill', d => colorMap[d.kind] || '#6b7280');
  node.append('text').attr('class', 'node-label').attr('dx', 12).attr('dy', 4)
    .text(d => d.id.replace(/^(tool:|resource:|sys:)/, '').substring(0, 25));

  // Tooltip
  const tooltip = d3.select('body').append('div').attr('class', 'tooltip').style('display', 'none');
  node.on('mouseover', (e, d) => {{
    tooltip.style('display', 'block').html(`<strong>${{d.id}}</strong><br>Kind: ${{d.kind}}`);
  }}).on('mousemove', (e) => {{
    tooltip.style('left', (e.pageX + 12) + 'px').style('top', (e.pageY - 20) + 'px');
  }}).on('mouseout', () => tooltip.style('display', 'none'));

  simulation.on('tick', () => {{
    link.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    node.attr('transform', d => `translate(${{d.x}},${{d.y}})`);
  }});
}}

// --- Donut Chart ---
function drawDonut() {{
  const svg = d3.select('#donut-svg');
  const w = 400, h = 400, r = 150;
  const g = svg.append('g').attr('transform', `translate(${{w/2}},${{h/2}})`);
  const colors = {{ critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e', info: '#6b7280' }};
  const data = Object.entries(severityCounts).filter(([,v]) => v > 0);
  const pie = d3.pie().value(d => d[1]);
  const arc = d3.arc().innerRadius(80).outerRadius(r);
  g.selectAll('path').data(pie(data)).join('path').attr('d', arc).attr('fill', d => colors[d.data[0]]).attr('stroke', 'var(--bg)').attr('stroke-width', 2);
  g.selectAll('text').data(pie(data)).join('text').attr('transform', d => `translate(${{arc.centroid(d)}})`).attr('text-anchor', 'middle').attr('fill', 'white').attr('font-size', '12px').attr('font-weight', '600').text(d => d.data[1] > 0 ? `${{d.data[0]}} (${{d.data[1]}})` : '');
  svg.append('text').attr('x', w/2).attr('y', h - 10).attr('text-anchor', 'middle').attr('fill', 'var(--text2)').attr('font-size', '13px').text('Findings by Severity');
}}

// --- Bar Chart ---
function drawBar() {{
  const svg = d3.select('#bar-svg');
  const margin = {{top: 20, right: 20, bottom: 40, left: 60}};
  const w = 500 - margin.left - margin.right, h = 400 - margin.top - margin.bottom;
  const g = svg.append('g').attr('transform', `translate(${{margin.left}},${{margin.top}})`);
  const colors = {{ critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e', info: '#6b7280' }};
  const data = Object.entries(severityCounts);
  const x = d3.scaleBand().domain(data.map(d => d[0])).range([0, w]).padding(0.3);
  const y = d3.scaleLinear().domain([0, d3.max(data, d => d[1]) || 1]).range([h, 0]);
  g.append('g').attr('transform', `translate(0,${{h}})`).call(d3.axisBottom(x)).selectAll('text').attr('fill', 'var(--text2)');
  g.append('g').call(d3.axisLeft(y).ticks(5)).selectAll('text').attr('fill', 'var(--text2)');
  g.selectAll('rect').data(data).join('rect').attr('x', d => x(d[0])).attr('y', d => y(d[1])).attr('width', x.bandwidth()).attr('height', d => h - y(d[1])).attr('fill', d => colors[d[0]]).attr('rx', 4);
  g.selectAll('.bar-label').data(data).join('text').attr('x', d => x(d[0]) + x.bandwidth()/2).attr('y', d => y(d[1]) - 6).attr('text-anchor', 'middle').attr('fill', 'var(--text)').attr('font-size', '12px').attr('font-weight', '600').text(d => d[1]);
  svg.append('text').attr('x', 280).attr('y', h + margin.top + margin.bottom - 2).attr('text-anchor', 'middle').attr('fill', 'var(--text2)').attr('font-size', '13px').text('Finding Count by Severity');
}}
</script>
</body>
</html>"""
