import streamlit as st
import streamlit.components.v1 as components
from streamlit import session_state as ss
import time
import random

import pandas as pd
import numpy as np
import os
import yaml
import json
from pathlib import Path

st.set_page_config(layout='wide', page_title="Nadomizer", page_icon='page_icon.png')

img_dir = Path("genshin_characters")
enemies_list = "enemies.yaml"
route_link = "https://qiqis-notebook.com/route/67a4b07f77537e1c51dc1f54"


# ── Session state init ───────────────────────────────────────────────────────

if "character_detail_df" not in ss:
    df = pd.read_csv('character_details.csv')
    df = df[['Name', 'Quality', 'Element', 'Weapon', 'Region', 'Model Type', 'Version']]
    df['Element'] = df['Element'].apply(lambda x: x[8:].split(" ")[0] if x == x else np.nan)
    df['Weapon'] = df['Weapon'].apply(lambda x: x[13:].split(" ")[1] if x == x else np.nan)
    df['Region'] = df['Region'].apply(lambda x: x.split(" ")[0] if x == x else np.nan)
    df['Selected'] = True
    ss.character_detail_df = df

if "characters" not in ss:
    ss.characters = [x[:-4] for x in os.listdir(str(img_dir))]

if "character_use_count" not in ss:
    ss.character_use_count = {c: 0 for c in ss.character_detail_df['Name'].unique()}

if "char_selected" not in ss:
    ss.char_selected = {c: True for c in ss.character_detail_df['Name'].tolist()}

if "team_size" not in ss:
    ss.team_size = 4

if "character_use_df" not in ss:
    ss.character_use_df = pd.DataFrame(
        columns=[f'Character{i+1}' for i in range(ss.team_size)] + ['LL/Weekly', 'Boss #']
    )

if "config" not in ss:
    with open(enemies_list, 'r') as f:
        config = yaml.safe_load(f)
    ss.config = config
    ss.LL = config['LL']
    ss.weeklies = config['weeklies']

if "enemies" not in ss:
    ss.enemies = ss.weeklies + ss.LL

if "wheel_names" not in ss:
    ss.wheel_names = list(ss.enemies)

if "team" not in ss:
    ss.team = random.sample(ss.characters, ss.team_size)

if "pending_boss" not in ss:
    ss.pending_boss = None

if "team_history" not in ss:
    ss.team_history = [ss.team]

if "team_history_idx" not in ss:
    ss.team_history_idx = 0

if "boss_counter" not in ss:
    ss.boss_counter = 0

if "pending_team_staged" not in ss:
    ss.pending_team_staged = None

if "active_filters" not in ss:
    ss.active_filters = {}


# ── Helpers ──────────────────────────────────────────────────────────────────

def format_time(seconds):
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    else:
        return f"{s}s"


def show_character_image(character):
    slug = "-".join(character.lower().split(" "))
    st.image(f"genshin_characters/{slug}.png")
    caption = (character[:10] + "...") if len(character) > 13 else character
    st.markdown(
        f"<p style='text-align:center; font-size:40px; color:white;'>{caption.title()}</p>",
        unsafe_allow_html=True
    )


def get_eligible_characters():
    return [
        c for c in ss.character_use_count
        if ss.character_use_count[c] < 3 and ss.char_selected.get(c, True)
    ]


def rebuild_use_df_columns():
    new_cols = [f'Character{i+1}' for i in range(ss.team_size)] + ['LL/Weekly', 'Boss #']
    if list(ss.character_use_df.columns) == new_cols:
        return
    old_df = ss.character_use_df.copy()
    new_df = pd.DataFrame(columns=new_cols)
    for _, row in old_df.iterrows():
        new_df.loc[len(new_df)] = {col: row[col] if col in row else "" for col in new_cols}
    ss.character_use_df = new_df


def generate_random_team(exclude_team=None):
    if exclude_team:
        for c in exclude_team:
            if c in ss.character_use_count and ss.character_use_count[c] > 0:
                ss.character_use_count[c] -= 1
    eligible = get_eligible_characters()
    if len(eligible) < ss.team_size:
        st.toast("Not enough eligible characters — resetting use counts")
        ss.character_use_count = {c: 0 for c in ss.character_use_count}
        eligible = get_eligible_characters()
    selected = random.sample(eligible, ss.team_size)
    for c in selected:
        ss.character_use_count[c] += 1
    return selected


def record_team(team, enemy="", boss_num=None):
    row = [c.title() for c in team] + [enemy, boss_num if boss_num else ""]
    ss.character_use_df.loc[len(ss.character_use_df)] = row


def push_team_history(team):
    ss.team_history = ss.team_history[:ss.team_history_idx + 1]
    ss.team_history.append(list(team))
    ss.team_history_idx = len(ss.team_history) - 1


def apply_filters_to_char_selected(new_filters):
    df = ss.character_detail_df
    mask = pd.Series([True] * len(df), index=df.index)
    for attr, values in new_filters.items():
        if values:
            mask &= df[attr].isin(values)
    for _, row in df.iterrows():
        name = row['Name']
        if not mask[row.name]:
            ss.char_selected[name] = False
        elif name not in ss.char_selected:
            ss.char_selected[name] = True


# ── Timer (uses st.html, no deprecated components.html) ─────────────────────

@st.fragment(run_every=0.1)
def timer():
    if "running" not in st.session_state:
        st.session_state.running = False
        st.session_state.start_time = None
        st.session_state.elapsed = 0

    elapsed = (
        time.time() - st.session_state.start_time
        if st.session_state.running
        else st.session_state.elapsed
    )

    time_str = format_time(elapsed)
    label = "⏹ Stop" if st.session_state.running else "▶ Start"
    status_color = "#4ade80" if st.session_state.running else "#94a3b8"
    status_text = "Running" if st.session_state.running else "Paused"
    pulse = "animation:pulse 1s infinite;" if st.session_state.running else ""

    st.html(f"""
        <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
        <style>@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.3}}}}</style>
        <div style="
            background:#0f172a; border:1px solid #1e293b; border-radius:10px;
            padding:12px 20px; font-family:'DM Sans',sans-serif;
            display:flex; align-items:center; justify-content:space-between;
            box-shadow:0 2px 16px rgba(0,0,0,0.4);
        ">
            <div>
                <div style="color:#64748b;font-size:10px;letter-spacing:.1em;text-transform:uppercase;margin-bottom:2px;">Elapsed</div>
                <div style="font-family:'DM Mono',monospace;font-size:28px;font-weight:500;color:#f1f5f9;letter-spacing:-1px;line-height:1;">{time_str}</div>
            </div>
            <span style="display:flex;align-items:center;gap:6px;color:{status_color};font-size:12px;">
                <span style="width:7px;height:7px;border-radius:50%;background:{status_color};{pulse}"></span>
                {status_text}
            </span>
        </div>
    """)

    tc1, tc2 = st.columns(2)
    with tc1:
        if st.button(label, use_container_width=True, key="timer_startstop"):
            if st.session_state.running:
                st.session_state.elapsed = time.time() - st.session_state.start_time
                st.session_state.running = False
            else:
                st.session_state.start_time = time.time() - st.session_state.elapsed
                st.session_state.running = True
    with tc2:
        if st.button("↺ Reset", use_container_width=True, key="timer_reset"):
            st.session_state.running = False
            st.session_state.start_time = None
            st.session_state.elapsed = 0


# ── Layout: left column (all content) | right column (map) ───────────────────

left, right = st.columns([1, 1])

with right:
    st.subheader("🗺 Qiqi's Notebook Route")
    st.iframe(route_link, height=1180)

with left:

    # ── Row 1: Timer + Team Size ─────────────────────────────────────────────
    r1a, r1b = st.columns([3, 1])
    with r1a:
        timer()
    with r1b:
        st.markdown("**Team size**")
        new_team_size = st.number_input(
            "Characters", min_value=1, max_value=10,
            value=ss.team_size, step=1,
            key="team_size_input", label_visibility="collapsed"
        )
        if st.button("Apply", use_container_width=True, key="apply_team_size"):
            if new_team_size != ss.team_size:
                ss.team_size = new_team_size
                rebuild_use_df_columns()
                eligible = get_eligible_characters()
                pool = eligible if len(eligible) >= ss.team_size else list(ss.character_use_count.keys())
                ss.team = random.sample(pool, ss.team_size)
                ss.team_history = [ss.team]
                ss.team_history_idx = 0
                ss.pending_team_staged = None
                st.rerun()

    st.divider()

    # ── Character Config (form, inside expander) ─────────────────────────────
    with st.expander("🎛 Character Config", expanded=False):
        filter_attrs = [c for c in ss.character_detail_df.columns if c not in ['Name', 'Selected']]

        # ── Phase 1: compute which names pass current active_filters ──────────
        df_all = ss.character_detail_df
        fmask = pd.Series([True] * len(df_all), index=df_all.index)
        for attr, values in ss.active_filters.items():
            if values:
                fmask &= df_all[attr].isin(values)
        filter_passing_names = sorted(df_all[fmask]['Name'].tolist())

        with st.form("char_config_form", border=False):
            # ── Step 1: Filters ───────────────────────────────────────────────
            st.markdown("**Step 1 — Filters** (AND logic across attributes, leave blank to include all)")
            pending_filters = {}
            attr_cols = st.columns(len(filter_attrs))
            for i, attr in enumerate(filter_attrs):
                with attr_cols[i]:
                    opts = sorted(df_all[attr].dropna().unique().tolist())
                    pending_filters[attr] = st.multiselect(
                        attr, options=opts,
                        default=ss.active_filters.get(attr, []),
                        key=f"filt_{attr}"
                    )

            st.divider()

            # ── Step 2: Per-character toggles (only filter-passing chars) ─────
            st.markdown(
                f"**Step 2 — Enable / Disable** — showing {len(filter_passing_names)} character(s) "
                "that pass current filters. Uncheck to exclude from rolls."
            )
            if filter_passing_names:
                n_cols = 5
                char_grid_cols = st.columns(n_cols)
                for idx, name in enumerate(filter_passing_names):
                    with char_grid_cols[idx % n_cols]:
                        st.checkbox(
                            name,
                            value=ss.char_selected.get(name, True),
                            key=f"chk_{name}"
                        )
            else:
                st.caption("No characters match the current filters.")

            st.divider()
            s1, s2 = st.columns(2)
            with s1:
                submitted = st.form_submit_button("✅ Apply Config", use_container_width=True, type="primary")
            with s2:
                clear_all = st.form_submit_button("↺ Reset All", use_container_width=True)

            if submitted:
                # Persist new filter selections
                new_filters = {k: v for k, v in pending_filters.items() if v}
                ss.active_filters = new_filters

                # Recompute which names pass the NEW filters
                new_fmask = pd.Series([True] * len(df_all), index=df_all.index)
                for attr, values in new_filters.items():
                    if values:
                        new_fmask &= df_all[attr].isin(values)
                new_passing = set(df_all[new_fmask]['Name'].tolist())

                # Force-deselect chars that don't pass the filter;
                # for chars that do pass, honour the checkbox the user just set.
                # Chars not shown at all (didn't pass OLD filter) keep their existing state.
                for name in df_all['Name'].tolist():
                    if name not in new_passing:
                        ss.char_selected[name] = False
                    elif name in filter_passing_names:
                        # Was shown — read checkbox value
                        ss.char_selected[name] = st.session_state.get(f"chk_{name}", True)
                    # else: wasn't shown in this render (filter changed), leave state as-is
                st.rerun()

            if clear_all:
                ss.active_filters = {}
                ss.char_selected = {n: True for n in ss.char_selected}
                st.rerun()

        # Summary outside form
        if ss.active_filters:
            parts = " | ".join(f"**{k}**: {', '.join(str(v) for v in vs)}" for k, vs in ss.active_filters.items())
            st.info(f"Active filters — {parts}")
        eligible_count = sum(1 for v in ss.char_selected.values() if v)
        st.metric("Eligible Characters", eligible_count)

    st.divider()

    # ── Boss pending banner ──────────────────────────────────────────────────
    if ss.pending_boss:
        st.info(f"⚔️ **{ss.pending_boss}** — generate a team you're happy with, then record.")
        rb, rrb, sb = st.columns(3)
        with rb:
            if st.button(f"✅ Record for {ss.pending_boss}", use_container_width=True, type="primary"):
                boss = ss.pending_boss
                ss.boss_counter += 1
                record_team(ss.team, enemy=boss, boss_num=ss.boss_counter)
                ss.pending_boss = None
                ss.pending_team_staged = None
                st.toast(f"Recorded team for {boss}! (Boss #{ss.boss_counter})")
                st.rerun()
        with rrb:
            if st.button("🔄 Reroll Team", use_container_width=True):
                new_team = generate_random_team(exclude_team=ss.pending_team_staged)
                push_team_history(new_team)
                ss.team = new_team
                ss.pending_team_staged = new_team
                st.toast("Rerolled!")
                st.rerun()
        with sb:
            if st.button("⏭ Skip Boss", use_container_width=True):
                if ss.pending_team_staged:
                    for c in ss.pending_team_staged:
                        if c in ss.character_use_count and ss.character_use_count[c] > 0:
                            ss.character_use_count[c] -= 1
                ss.pending_boss = None
                ss.pending_team_staged = None
                st.rerun()

    # ── Team display ─────────────────────────────────────────────────────────
    st.subheader("Current Team")
    team_cols = st.columns(ss.team_size)
    for character, i in zip(ss.team, range(ss.team_size)):
        with team_cols[i]:
            show_character_image(character)

    can_go_prev = ss.team_history_idx > 0
    can_go_next = ss.team_history_idx < len(ss.team_history) - 1
    nav1, nav2, nav3 = st.columns(3)
    with nav1:
        if st.button("⬅ Prev", use_container_width=True, disabled=not can_go_prev):
            ss.team_history_idx -= 1
            ss.team = list(ss.team_history[ss.team_history_idx])
            st.rerun()
    with nav2:
        if st.button("🎲 Generate Team", use_container_width=True, type="primary"):
            new_team = generate_random_team()
            push_team_history(new_team)
            ss.team = new_team
            if ss.pending_boss:
                ss.pending_team_staged = new_team
            st.rerun()
    with nav3:
        if st.button("➡ Next", use_container_width=True, disabled=not can_go_next):
            ss.team_history_idx += 1
            ss.team = list(ss.team_history[ss.team_history_idx])
            st.rerun()

    st.caption(f"Team {ss.team_history_idx + 1} / {len(ss.team_history)} — navigation does not affect use counts")

    if not ss.pending_boss:
        if st.button("📝 Record Team (no boss)", use_container_width=True):
            record_team(ss.team, enemy="", boss_num="")
            st.toast("Team recorded with no boss.")
            st.rerun()

    with st.expander("📊 Character Use Counts"):
        display_df = pd.DataFrame(
            [(c, ss.character_use_count[c]) for c in ss.character_use_count],
            columns=['Character', 'Use Count']
        ).sort_values('Use Count', ascending=False).reset_index(drop=True)
        st.dataframe(display_df, use_container_width=True)

    st.divider()

    # ── Team History ─────────────────────────────────────────────────────────
    st.subheader("📋 Team History")
    if ss.character_use_df.empty:
        st.caption("No teams recorded yet.")
    else:
        st.dataframe(ss.character_use_df, use_container_width=True)

    st.divider()

    # ── Boss Wheel ───────────────────────────────────────────────────────────
    st.subheader("🎡 LL/Weekly Boss Selector")

    with st.expander("⚙️ Configure Wheel"):
        with st.form("wheel_config_form"):
            wc1, wc2 = st.columns(2)
            with wc1:
                weeklies_toggle = st.checkbox("Weekly Bosses", value=True)
            with wc2:
                LL_toggle = st.checkbox("LL Bosses", value=True)
            if st.form_submit_button("Confirm Config", help="Also resets the wheel"):
                ss.enemies = (
                    (ss.weeklies if weeklies_toggle else []) +
                    (ss.LL if LL_toggle else [])
                )
                ss.wheel_names = list(ss.enemies)
                ss.pop("wheel_winner", None)
                ss.pop("wheel_trigger", None)

    def spin_wheel(names: list) -> str | None:
        if "wheel_winner" not in st.session_state:
            st.session_state.wheel_winner = None
        if "wheel_trigger" not in st.session_state:
            st.session_state.wheel_trigger = 0

        sc1, _ = st.columns([1, 4])
        if sc1.button("▶ Spin", key="spin_btn"):
            if not names:
                st.toast("No bosses left to spin!")
            else:
                chosen = random.choice(names)
                st.session_state.wheel_winner = chosen
                st.session_state.wheel_trigger += 1
                ss.pending_boss = chosen
                ss.pending_team_staged = None
                if chosen in ss.enemies:
                    ss.enemies.remove(chosen)

        winner = st.session_state.wheel_winner
        trigger = st.session_state.wheel_trigger
        names_json = json.dumps(names)
        winner_json = json.dumps(winner)

        # Wheel canvas — components.html required for JS canvas execution
        components.html(f"""
            <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600&display=swap" rel="stylesheet">
            <div style="display:flex;flex-direction:column;align-items:center;">
            <canvas id="wheel" width="700" height="700" style="max-width:100%;"></canvas>
            </div>
            <script>
                (function() {{
                    const names   = {names_json};
                    const winner  = {winner_json};
                    const trigger = {trigger};
                    const canvas  = document.getElementById("wheel");
                    const ctx     = canvas.getContext("2d");
                    const cx = canvas.width / 2, cy = canvas.height / 2;
                    const radius = cx - 10;
                    const TWO_PI = 2 * Math.PI;
                    const arc    = TWO_PI / names.length;
                    const colors = ["#e63946","#f4a261","#e9c46a","#2a9d8f","#457b9d","#a8dadc","#e76f51","#8ecae6","#c77dff","#06d6a0","#ffd166","#ef476f"];

                    function drawWheel(angle) {{
                        ctx.clearRect(0, 0, canvas.width, canvas.height);
                        names.forEach((name, i) => {{
                            const start = angle + i * arc, end = start + arc;
                            ctx.beginPath(); ctx.moveTo(cx, cy);
                            ctx.arc(cx, cy, radius, start, end); ctx.closePath();
                            ctx.fillStyle = colors[i % colors.length]; ctx.fill();
                            ctx.strokeStyle = "#0f172a"; ctx.lineWidth = 2; ctx.stroke();
                            ctx.save(); ctx.translate(cx, cy); ctx.rotate(start + arc / 2);
                            ctx.textAlign = "right"; ctx.fillStyle = "#f1f5f9";
                            ctx.font = "600 18px 'DM Sans', sans-serif";
                            const label = name.length > 14 ? name.slice(0, 14) + "\u2026" : name;
                            ctx.fillText(label, radius - 12, 6); ctx.restore();
                        }});
                        ctx.beginPath(); ctx.arc(cx, cy, 16, 0, TWO_PI);
                        ctx.fillStyle = "#0f172a"; ctx.fill();
                        ctx.strokeStyle = "#334155"; ctx.lineWidth = 2; ctx.stroke();
                        ctx.beginPath();
                        ctx.moveTo(canvas.width - 4, cy);
                        ctx.lineTo(canvas.width - 22, cy - 9);
                        ctx.lineTo(canvas.width - 22, cy + 9);
                        ctx.closePath(); ctx.fillStyle = "#f1f5f9"; ctx.fill();
                    }}

                    function spinToWinner() {{
                        const winnerIndex = names.indexOf(winner);
                        if (winnerIndex === -1) {{ drawWheel(0); return; }}
                        const finalAngle  = -(winnerIndex * arc + arc / 2);
                        const extraSpins  = -(6 + Math.floor(Math.random() * 4)) * TWO_PI;
                        const targetAngle = finalAngle + extraSpins;
                        const duration    = 4000;
                        const startTime   = performance.now();
                        function easeOut(t) {{ return 1 - Math.pow(1 - t, 4); }}
                        function animate(now) {{
                            const t = Math.min((now - startTime) / duration, 1);
                            drawWheel(targetAngle * easeOut(t));
                            if (t < 1) requestAnimationFrame(animate);
                            else drawWheel(targetAngle);
                        }}
                        requestAnimationFrame(animate);
                    }}

                    if (trigger > 0 && winner) spinToWinner();
                    else drawWheel(0);
                }})();
            </script>
        """, height=720)

        return winner if trigger > 0 else None

    winner = spin_wheel(ss.wheel_names)

    if winner is not None:
        ss.wheel_names = list(ss.enemies)
        time.sleep(4)
        st.success(f"🏆 **{winner}** selected! Generate a team above and hit Record.")