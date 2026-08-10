"""Generate a styled ER diagram straight from the SQLAlchemy metadata."""
from flask import Flask
from app.config import Config
from app.extensions import db
from app import models

HIDE = {
 "user": {"fs_webauthn_user_handle","mf_recovery_codes","us_phone_number","username",
          "us_totp_secrets","confirmed_at","last_login_at","current_login_at",
          "last_login_ip","current_login_ip","login_count","tf_primary_method",
          "tf_totp_secret","tf_phone_number","create_datetime","update_datetime"},
 "role": {"permissions","update_datetime"},
}
ORDER = ["id","email","password","active","fs_uniquifier","full_name","phone",
         "is_blacklisted","created_at"]

HDR, BODY, ALT, LINE, MUTED = "#2f5d7c", "#ffffff", "#f4f7f9", "#9fb3c0", "#7b8f9c"

def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def short(t):
    t = str(t)
    for a,b in (("VARCHAR","str"),("INTEGER","int"),("DATETIME","datetime"),
                ("BOOLEAN","bool"),("TEXT","text"),("FLOAT","float"),("DATE","date")):
        t = t.replace(a,b)
    return t.split("(")[0] if t.startswith("str") and "(" in t else t

app = Flask(__name__); app.config.from_object(Config)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
db.init_app(app)

with app.app_context():
    db.create_all()
    md = db.metadata
    out = ['digraph ER {',
           '  graph [rankdir=LR, splines=spline, nodesep=0.40, ranksep=0.85, bgcolor="white", pad=0.35, dpi=160];',
           f'  node [shape=plaintext, fontname="DejaVu Sans", fontsize=11];',
           f'  edge [color="{LINE}", penwidth=1.4, arrowsize=0.9, fontname="DejaVu Sans", fontsize=9, fontcolor="{MUTED}"];']

    for name in sorted(md.tables):
        table = md.tables[name]
        hidden = HIDE.get(name, set())
        cols = [c for c in table.columns if c.name not in hidden]
        if name == "user":
            cols.sort(key=lambda c: ORDER.index(c.name) if c.name in ORDER else 99)
        rows = [f'<TR><TD BGCOLOR="{HDR}" COLSPAN="3" ALIGN="CENTER">'
                f'<FONT COLOR="white" POINT-SIZE="13"><B>  {esc(name)}  </B></FONT></TD></TR>']
        for i, c in enumerate(cols):
            fks = list(c.foreign_keys)
            tag = "PK" if c.primary_key else ("FK" if fks else "")
            bg = BODY if i % 2 == 0 else ALT
            nm = f"<B>{esc(c.name)}</B>" if c.primary_key else esc(c.name)
            rows.append(
                f'<TR>'
                f'<TD BGCOLOR="{bg}" ALIGN="LEFT" PORT="{esc(c.name)}"> {nm} </TD>'
                f'<TD BGCOLOR="{bg}" ALIGN="LEFT"><FONT COLOR="{MUTED}" POINT-SIZE="9">{esc(short(c.type))} </FONT></TD>'
                f'<TD BGCOLOR="{bg}" ALIGN="RIGHT">' + (f'<FONT COLOR="{MUTED}" POINT-SIZE="8"><B>{tag}</B> </FONT>' if tag else ' ') + '</TD>'
                f'</TR>')
        label = ('<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" '
                 f'BGCOLOR="{LINE}" STYLE="ROUNDED">' + "".join(rows) + '</TABLE>>')
        out.append(f'  "{name}" [label={label}];')

    # crow's foot: tee = exactly one, crow = many
    for name in sorted(md.tables):
        for c in md.tables[name].columns:
            for fk in c.foreign_keys:
                parent = fk.column.table.name
                out.append(f'  "{parent}":"{fk.column.name}" -> "{name}":"{c.name}" '
                           f'[dir=both, arrowtail=tee, arrowhead=crow];')
    out.append("}")
    open("/tmp/er.dot","w").write("\n".join(out))
    print("dot written,", len(md.tables), "tables")
