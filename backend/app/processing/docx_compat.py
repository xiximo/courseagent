from __future__ import annotations

_applied = False


def apply_python_docx_compat() -> None:
    """跳过 python-docx 无法加载的损坏关系（NULL、内部书签等）。"""
    global _applied
    if _applied:
        return

    from docx.opc.oxml import parse_xml
    from docx.opc.pkgreader import _SerializedRelationship, _SerializedRelationships

    def load_from_xml_compat(base_uri, rels_item_xml):
        srels = _SerializedRelationships()
        if rels_item_xml is None:
            return srels

        rels_elm = parse_xml(rels_item_xml)
        for rel_elm in rels_elm.Relationship_lst:
            target = rel_elm.target_ref
            if target in ("../NULL", "NULL"):
                continue
            if target.startswith("#"):
                continue
            srels._srels.append(_SerializedRelationship(base_uri, rel_elm))
        return srels

    _SerializedRelationships.load_from_xml = load_from_xml_compat
    _applied = True
