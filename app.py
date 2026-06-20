import os
import json
import re
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def load_characters():
    with open(os.path.join(DATA_DIR, "characters.json"), encoding="utf-8") as f:
        return json.load(f)

def get_character(char_data, name):
    for c in char_data["characters"]:
        if c["name"] == name:
            return c
    return None

def build_prompt(character_name, discs, char_info):
    discs_text = ""
    for i, disc in enumerate(discs, 1):
        substats_text = ""
        for s in disc.get("substats", []):
            if s.get("name") and s.get("value"):
                substats_text += f"    - {s['name']}: {s['value']}\n"
        discs_text += f"""
{i}号位驱动盘：
  套装：{disc.get('set_name', '未填写')}
  主属性：{disc.get('main_stat', '未填写')}
  副属性：
{substats_text if substats_text else '    （未填写）'}"""

    if char_info:
        char_context = f"""
角色定位：{char_info.get('positioning', '')}
推荐套装：{', '.join(char_info.get('recommended_sets', []))}
推荐主属性（4号位）：{', '.join(char_info.get('main_stats', {}).get('4', []))}
推荐主属性（5号位）：{', '.join(char_info.get('main_stats', {}).get('5', []))}
推荐主属性（6号位）：{', '.join(char_info.get('main_stats', {}).get('6', []))}
优先副属性：{', '.join(char_info.get('priority_substats', []))}
副属性备注：{char_info.get('substat_notes', '')}"""
    else:
        char_context = "（未找到该角色的预设数据，请根据通用规则评分）"

    prompt = f"""你是绝区零（Zenless Zone Zero）的驱动盘评分专家。请对以下角色的驱动盘配装进行专业评分。

## 角色信息
角色名：{character_name}
{char_context}

## 驱动盘数据
{discs_text}

## 评分规则
1. **套装适配性**（每个盘20%权重）：推荐套装得高分，非推荐套装扣分。注意2件套和4件套的搭配逻辑。
2. **主属性匹配**（每个盘30%权重）：主属性是否符合角色推荐。1-3号位固定，4-6号位重点评估。
3. **副属性有效条数**（每个盘50%权重）：
   - 完全有效词条（优先副属性列表中的）：每条+2分
   - 部分有效词条：每条+1分
   - 无效词条：不加分
   - 副属性数值高低也影响分数（高数值加成）
4. **综合评分**：综合6个盘的情况，考虑整体套装搭配效果

## 输出要求
请严格按以下JSON格式输出，不要添加任何其他文字：

{{
  "overall_score": <1-100的整数>,
  "overall_grade": "<S/A/B/C/D级>",
  "overall_comment": "<2-3句综合评价>",
  "discs": [
    {{
      "slot": 1,
      "score": <1-100整数>,
      "grade": "<S/A/B/C/D>",
      "set_eval": "<套装评价，1句>",
      "main_stat_eval": "<主属性评价，1句>",
      "substat_eval": "<副属性评价，1-2句>",
      "effective_substats": <有效词条数0-4>,
      "comment": "<该盘总结，1句>"
    }}
    // 重复6个盘
  ],
  "suggestions": [
    "<改进建议1>",
    "<改进建议2>",
    "<改进建议3>"
  ],
  "priority_upgrades": "<最优先强化/替换哪个盘，1句>"
}}

评分参考：S级(90-100)=完美毕业，A级(75-89)=优秀可用，B级(60-74)=良好，C级(40-59)=勉强可用，D级(0-39)=建议替换。
"""
    return prompt

def call_ai_api(prompt, provider=None, api_key=None, api_base=None, model=None):
    import urllib.request

    if provider == "claude":
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("未配置 Claude API Key，请在设置中填写或设置 ANTHROPIC_API_KEY 环境变量")
        base = api_base or "https://api.anthropic.com"
        mdl = model or "claude-haiku-4-5-20251001"
        return call_claude(prompt, key, base, mdl)

    # openai / custom / 未指定 → 走 OpenAI 兼容接口
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if key:
        base = api_base or "https://api.openai.com"
        mdl = model or "gpt-4o-mini"
        return call_openai(prompt, key, base, mdl)

    # 最后 fallback：Claude 环境变量
    claude_key = os.environ.get("ANTHROPIC_API_KEY")
    if claude_key:
        return call_claude(prompt, claude_key, "https://api.anthropic.com", "claude-haiku-4-5-20251001")

    raise ValueError("未配置 API Key，请在页面右上角设置中填写，或设置 OPENAI_API_KEY / ANTHROPIC_API_KEY 环境变量")

def call_openai(prompt, api_key, base_url="https://api.openai.com", model="gpt-4o-mini"):
    import urllib.request
    url = base_url.rstrip("/") + "/v1/chat/completions"
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 2000
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    return result["choices"][0]["message"]["content"]

def call_claude(prompt, api_key, base_url="https://api.anthropic.com", model="claude-haiku-4-5-20251001"):
    import urllib.request
    url = base_url.rstrip("/") + "/v1/messages"
    data = json.dumps({
        "model": model,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    return result["content"][0]["text"]

def parse_ai_response(text):
    # 从 AI 响应中提取 JSON
    text = text.strip()
    # 去掉 markdown 代码块
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # 移除 JSON 中的注释行（// ...）
    text = re.sub(r"//[^\n]*", "", text)
    return json.loads(text)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/characters")
def api_characters():
    data = load_characters()
    return jsonify(data)

@app.route("/api/score", methods=["POST"])
def api_score():
    body = request.get_json()
    if not body:
        return jsonify({"error": "请求体为空"}), 400

    character_name = body.get("character", "").strip()
    discs = body.get("discs", [])

    if not character_name:
        return jsonify({"error": "请选择角色"}), 400
    if len(discs) != 6:
        return jsonify({"error": "请填写全部6个驱动盘"}), 400

    char_data = load_characters()
    char_info = get_character(char_data, character_name)

    prompt = build_prompt(character_name, discs, char_info)

    provider = body.get("provider", "")
    api_key = body.get("api_key", "").strip() or None
    api_base = body.get("api_base", "").strip() or None
    model = body.get("model", "").strip() or None

    try:
        raw = call_ai_api(prompt, provider=provider, api_key=api_key, api_base=api_base, model=model)
        result = parse_ai_response(raw)
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except json.JSONDecodeError:
        return jsonify({"error": "AI 返回格式异常，请重试", "raw": raw}), 500
    except Exception as e:
        return jsonify({"error": f"API 调用失败：{str(e)}"}), 500

    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
