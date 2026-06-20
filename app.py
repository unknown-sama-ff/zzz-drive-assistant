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

SET_EFFECTS = {
    "极地重金属":     {"2pc": "冰属性伤害+10%", "4pc": "触发冻结/碎冰/霜冻时，冰属性伤害额外+20%，技能伤害+25%"},
    "震星迪斯科":     {"2pc": "冲击力+6", "4pc": "命中弱点后异常积累+20%，持续6秒"},
    "啄木鸟电音":     {"2pc": "暴击率+8%", "4pc": "暴击后攻击力+8%，最多叠3层，持续6秒"},
    "骑士的征战之路": {"2pc": "护盾效果+15%", "4pc": "自身护盾期间，全队伤害+15%"},
    "自由蓝调":       {"2pc": "异常精通+15", "4pc": "触发异常后，目标异常抗性-10%，持续8秒"},
    "混沌爵士":       {"2pc": "全队异常精通+15", "4pc": "使用连携技或终结技后，全队攻击力+15%"},
    "暗夜使者":       {"2pc": "物理伤害+10%", "4pc": "对侵蚀/混乱状态目标，物理伤害额外+35%"},
    "破晓之辉":       {"2pc": "能量自动回复+15%", "4pc": "释放终结技后，全队攻击力+25%，持续12秒"},
    "奥博斯实验室":   {"2pc": "能量自动回复+15%", "4pc": "使用EX特殊攻击后，全队攻击力+15%，持续12秒"},
    "原初暗岩":       {"2pc": "火属性伤害+10%", "4pc": "持续攻击同一目标时，火伤额外最高+28%"},
    "星光骑士":       {"2pc": "攻击力+10%", "4pc": "暴击率越高，伤害加成越高，最高+56%"},
    "聚变机启":       {"2pc": "电属性伤害+10%", "4pc": "释放EX特殊攻击或连携技后，暴击伤害+20%，持续8秒"},
    "归航信标":       {"2pc": "生命值+10%", "4pc": "使用闪避反击后，生命值低于50%时触发治疗"},
    "混响金属":       {"2pc": "冲击力+6", "4pc": "击破后全队攻击力+20%，持续10秒"},
}

ROLE_WEIGHTS = {
    "主C":    {"set": 15, "main": 25, "sub": 60},
    "副C":    {"set": 15, "main": 25, "sub": 60},
    "副C/击破":{"set": 20, "main": 25, "sub": 55},
    "副C/异常":{"set": 20, "main": 20, "sub": 60},
    "辅助":   {"set": 20, "main": 30, "sub": 50},
    "辅助/控制":{"set": 20, "main": 30, "sub": 50},
    "辅助/坦克":{"set": 20, "main": 30, "sub": 50},
    "辅助/减防":{"set": 20, "main": 30, "sub": 50},
    "辅助/击破":{"set": 20, "main": 25, "sub": 55},
    "辅助/异常":{"set": 20, "main": 25, "sub": 55},
}

SUBSTAT_THRESHOLDS = {
    "暴击率%":    {"high": 7.2, "mid": 4.8, "low": 2.4,  "unit": "%"},
    "暴击伤害%":  {"high": 14.4,"mid": 9.6, "low": 4.8,  "unit": "%"},
    "攻击力%":    {"high": 9.0, "mid": 6.0, "low": 3.0,  "unit": "%"},
    "攻击力数值": {"high": 60,  "mid": 40,  "low": 20,   "unit": ""},
    "防御力%":    {"high": 9.6, "mid": 6.4, "low": 3.2,  "unit": "%"},
    "防御力数值": {"high": 70,  "mid": 46,  "low": 23,   "unit": ""},
    "生命值%":    {"high": 9.0, "mid": 6.0, "low": 3.0,  "unit": "%"},
    "生命值数值": {"high": 600, "mid": 400, "low": 200,  "unit": ""},
    "穿透值":     {"high": 36,  "mid": 24,  "low": 12,   "unit": ""},
    "异常精通":   {"high": 12,  "mid": 8,   "low": 4,    "unit": ""},
    "异常掌控":   {"high": 12,  "mid": 8,   "low": 4,    "unit": ""},
    "能量自动回复":{"high": 12, "mid": 8,   "low": 4,    "unit": ""},
}

def build_prompt(character_name, discs, char_info):
    role = char_info.get("role", "主C") if char_info else "主C"
    weights = ROLE_WEIGHTS.get(role, {"set": 15, "main": 25, "sub": 60})

    # Build set usage summary for synergy analysis
    set_counter = {}
    for d in discs:
        s = d.get("set_name", "").strip()
        if s:
            set_counter[s] = set_counter.get(s, 0) + 1

    set_summary_lines = []
    for s, cnt in set_counter.items():
        effect = SET_EFFECTS.get(s, {})
        active = []
        if cnt >= 2 and effect.get("2pc"):
            active.append(f"2件套激活：{effect['2pc']}")
        if cnt >= 4 and effect.get("4pc"):
            active.append(f"4件套激活：{effect['4pc']}")
        if active:
            set_summary_lines.append(f"  - {s}×{cnt}：{' | '.join(active)}")
        else:
            set_summary_lines.append(f"  - {s}×{cnt}：{'（效果未知，请据实评估）' if s not in SET_EFFECTS else '（未达激活件数）'}")
    set_summary = "\n".join(set_summary_lines) if set_summary_lines else "  （未填写套装）"

    # Build disc text
    discs_text = ""
    for i, disc in enumerate(discs, 1):
        substats_text = ""
        for sub in disc.get("substats", []):
            if sub.get("name") and sub.get("value"):
                name = sub["name"]
                val = sub["value"]
                thr = SUBSTAT_THRESHOLDS.get(name)
                if thr:
                    try:
                        v = float(str(val).replace("%", ""))
                        if v >= thr["high"]:
                            quality = "★高档"
                        elif v >= thr["mid"]:
                            quality = "★中档"
                        else:
                            quality = "低档"
                    except Exception:
                        quality = "未知"
                    substats_text += f"    - {name}: {val}  [{quality}，参考区间: 低<{thr['mid']}{thr['unit']} 中{thr['mid']}-{thr['high']}{thr['unit']} 高≥{thr['high']}{thr['unit']}]\n"
                else:
                    substats_text += f"    - {name}: {val}\n"
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

    prompt = f"""你是绝区零（Zenless Zone Zero）3.0版本的驱动盘评分专家，熟悉当前版本强度梯队与主流配装方案。

## 角色信息
角色名：{character_name}
角色定位：{role}
{char_context}

## 当前套装激活效果
{set_summary}

## 驱动盘数据（副属性已标注档位供参考）
{discs_text}

## 评分权重（根据角色定位 {role} 动态调整）
- 套装适配性：{weights['set']}%
- 主属性匹配：{weights['main']}%
- 副属性质量：{weights['sub']}%

## 详细评分规则

### 1. 套装适配性（{weights['set']}%）
- 4件套推荐套装且激活效果契合角色：满分
- 2+2件套（双2件套）且均为推荐套装：-5分
- 含1个推荐套装2件套 + 1个非推荐套装：-10~15分
- 套装完全不符合角色定位：-20分以上
- 评估2+4件套的整体协同效应，优质的2+2有时优于错误的4件套

### 2. 主属性匹配（{weights['main']}%）
- 4/5/6号位主属性是否符合推荐，1-3号位固定不作主要评分点
- 主属性完全正确：满分；次优选择：-5~10分；错误主属性：-20分以上

### 3. 副属性质量（{weights['sub']}%）
- 副属性档位（已标注★高档/★中档/低档）直接影响得分
- 有效词条（在优先副属性列表中）：
  - ★高档有效词条：每条+3分
  - ★中档有效词条：每条+2分
  - 低档有效词条：每条+1分
- 次要有效词条（有用但非优先）：
  - ★高档：每条+1.5分；★中档：每条+1分；低档：+0.5分
- 无效词条：0分
- 副属性总数不足4条：酌情扣分

## 评分参考
S级(90-100)：毕业级，绝大多数词条有效且档位高
A级(75-89)：优秀可用，主要词条有效，部分档位偏低
B级(60-74)：良好，有效词条过半，仍有替换价值
C级(40-59)：勉强可用，有效词条较少
D级(0-39)：建议优先替换

## 版本强度参考（3.0版本）
请根据角色在3.0版本的强度梯队（T0/T1/T2）给出meta_tier评级：
- T0：当前版本顶尖，通关首选
- T1：强力，主流队伍常见
- T2：可用，非最优选择

## 输出要求
请严格按以下JSON格式输出，不要添加任何其他文字：

{{
  "overall_score": <1-100的整数>,
  "overall_grade": "<S/A/B/C/D>",
  "meta_tier": "<T0/T1/T2>",
  "overall_comment": "<2-3句综合评价>",
  "set_synergy": "<套装搭配整体评价，说明2/4件套激活情况和协同效果，1-2句>",
  "discs": [
    {{
      "slot": 1,
      "score": <1-100整数>,
      "grade": "<S/A/B/C/D>",
      "set_eval": "<套装评价，1句>",
      "main_stat_eval": "<主属性评价，1句>",
      "substat_eval": "<副属性评价，说明有效词条数量和档位，1-2句>",
      "effective_substats": <有效词条数0-4>,
      "comment": "<该盘总结，1句>"
    }}
  ],
  "suggestions": [
    "<改进建议1>",
    "<改进建议2>",
    "<改进建议3>"
  ],
  "priority_upgrades": "<最优先强化/替换哪个盘及原因，1句>"
}}
"""
    return prompt

def call_ai_api(prompt, provider=None, api_key=None, api_base=None, model=None):
    import urllib.request

    if provider == "claude":
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("未配置 Claude API Key，请在设置中填写或设置 ANTHROPIC_API_KEY 环境变量")
        base = api_base or os.environ.get("ANTHROPIC_API_BASE") or "https://api.anthropic.com"
        mdl = model or os.environ.get("ANTHROPIC_MODEL") or "claude-haiku-4-5-20251001"
        return call_claude(prompt, key, base, mdl)

    if provider == "deepseek":
        key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise ValueError("未配置 DeepSeek API Key，请在设置中填写或设置 DEEPSEEK_API_KEY 环境变量")
        base = api_base or os.environ.get("DEEPSEEK_API_BASE") or "https://api.deepseek.com"
        mdl = model or os.environ.get("DEEPSEEK_MODEL") or "deepseek-chat"
        return call_openai(prompt, key, base, mdl)

    # openai / custom / 未指定 → 走 OpenAI 兼容接口
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if key:
        base = api_base or os.environ.get("OPENAI_API_BASE") or "https://api.openai.com"
        mdl = model or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
        return call_openai(prompt, key, base, mdl)

    # fallback: DeepSeek 环境变量
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    if deepseek_key:
        base = os.environ.get("DEEPSEEK_API_BASE") or "https://api.deepseek.com"
        mdl = os.environ.get("DEEPSEEK_MODEL") or "deepseek-chat"
        return call_openai(prompt, deepseek_key, base, mdl)

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
