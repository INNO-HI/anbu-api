"""anbu 운영 CLI — 모든 과업 기능의 명령행 진입점.

사용 예:
  .venv/bin/python -m anbu_api.cli init-db
  .venv/bin/python -m anbu_api.cli seed --subjects 6 --days 2
  .venv/bin/python -m anbu_api.cli diag --out build/서버진단보고서.md
  .venv/bin/python -m anbu_api.cli etl intervals
  .venv/bin/python -m anbu_api.cli dictionary --out-dir build
  .venv/bin/python -m anbu_api.cli ami-load
  .venv/bin/python -m anbu_api.cli pseudo-run [--include-memo]
  .venv/bin/python -m anbu_api.cli freetext-test --out build/재식별시험결과서.md
  .venv/bin/python -m anbu_api.cli publish --dry-run
  .venv/bin/python -m anbu_api.cli create-user --username admin --role super_admin
  .venv/bin/python -m anbu_api.cli gen-acl --out deploy/mosquitto/config/acl
  .venv/bin/python -m anbu_api.cli serve
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys

from anbu_api.db import get_session, init_db


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def cmd_init_db(args) -> None:
    init_db()
    print("DB 초기화 완료 (accum / transfer / ops)")


def cmd_seed(args) -> None:
    from anbu_api.seed import seed_accum

    session = get_session("accum")
    try:
        _print(seed_accum(session, subjects=args.subjects, days=args.days))
    finally:
        session.close()


def cmd_diag(args) -> None:
    from anbu_api.diagnostics.server_diag import run_diagnostics, write_report

    session = get_session("accum")
    try:
        diag = run_diagnostics(session, data_dir=args.data_dir)
    finally:
        session.close()
    if args.out:
        print(f"보고서 생성: {write_report(diag, args.out)}")
    else:
        _print(diag)


def cmd_etl(args) -> None:
    session = get_session("accum")
    try:
        if args.job == "intervals":
            from anbu_api.etl.lighting_intervals import build_intervals
            _print({"created": build_intervals(session)})
        elif args.job == "status":
            from anbu_api.etl.device_status_history import sync_status
            _print({"appended": sync_status(session)})
        elif args.job == "inactivity":
            from anbu_api.etl.device_status_history import infer_inactivity
            _print({"changed": infer_inactivity(session)})
        elif args.job == "retention":
            from anbu_api.etl.retention import apply_retention
            _print(apply_retention(session))
    finally:
        session.close()


def cmd_dictionary(args) -> None:
    from anbu_api.dictionary.generate import generate_dictionary

    session = get_session("accum")
    try:
        for path in generate_dictionary(args.out_dir, accum_session=session):
            print(f"생성: {path}")
    finally:
        session.close()


def cmd_ami_load(args) -> None:
    from anbu_api.ami.loader import integrate_ami
    from anbu_api.pseudonym.mapping_store import MappingStore

    accum, ops = get_session("accum"), get_session("ops")
    try:
        _print({"added": integrate_ami(accum, MappingStore(ops))})
    finally:
        accum.close()
        ops.close()


def cmd_pseudo_run(args) -> None:
    from anbu_api.pseudonym.pipeline import run_full, write_processing_record

    accum, transfer, ops = get_session("accum"), get_session("transfer"), get_session("ops")
    try:
        memo_fn = None
        if args.include_memo:
            from anbu_api.freetext.pseudonymizer import FreeTextPseudonymizer, build_known_names

            p = FreeTextPseudonymizer(build_known_names(accum))
            memo_fn = lambda text: p.pseudonymize(text).text  # noqa: E731
        counts = run_full(accum, transfer, ops, memo_pseudonymizer=memo_fn)
        _print(counts)
        if args.record:
            print(f"처리 기록: {write_processing_record(counts, args.record)}")
    finally:
        accum.close(); transfer.close(); ops.close()


def cmd_freetext_test(args) -> None:
    from anbu_api.freetext.reident_test import run_reident_test, write_report
    from anbu_api.freetext.review import build_review_sheet, write_review_record

    accum, transfer = get_session("accum"), get_session("transfer")
    try:
        result = run_reident_test(accum, transfer)
        _print(result)
        if args.out:
            print(f"재식별 시험 결과서: {write_report(result, args.out)}")
        if args.review_sheet:
            stats = build_review_sheet(transfer, args.review_sheet)
            _print(stats)
            if args.review_record:
                print(f"추가검수 기록: {write_review_record(stats, args.review_record)}")
    finally:
        accum.close(); transfer.close()


def cmd_publish(args) -> None:
    from anbu_api.transport.mqtt_publisher import publish_all, publish_table

    transfer, ops = get_session("transfer"), get_session("ops")
    try:
        if args.table:
            _print({args.table: publish_table(transfer, ops, args.table, dry_run=args.dry_run)})
        else:
            _print(publish_all(transfer, ops, dry_run=args.dry_run))
    finally:
        transfer.close(); ops.close()


def cmd_create_user(args) -> None:
    from anbu_api.api.auth import hash_password
    from anbu_api.models.ops import User

    password = args.password or getpass.getpass("비밀번호: ")
    ops = get_session("ops")
    try:
        ops.add(User(username=args.username, password_hash=hash_password(password),
                     role=args.role))
        ops.commit()
        print(f"계정 생성: {args.username} ({args.role})")
    finally:
        ops.close()


def cmd_gen_acl(args) -> None:
    from anbu_api.transport.acl import generate_mosquitto_acl

    ops = get_session("ops")
    try:
        print(f"ACL 생성: {generate_mosquitto_acl(ops, args.out)}")
    finally:
        ops.close()


def cmd_serve(args) -> None:
    import uvicorn

    uvicorn.run("anbu_api.api.main:app", host=args.host, port=args.port)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="anbu", description="제주 안부똑똑 데이터 관리·전송 체계 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="세 DB 테이블 생성").set_defaults(func=cmd_init_db)

    p = sub.add_parser("seed", help="개발용 합성 데이터 적재(운영 금지)")
    p.add_argument("--subjects", type=int, default=6)
    p.add_argument("--days", type=int, default=1)
    p.set_defaults(func=cmd_seed)

    p = sub.add_parser("diag", help="서버 진단(SFR-001)")
    p.add_argument("--out", help="진단 보고서(markdown) 출력 경로")
    p.add_argument("--data-dir", default=".")
    p.set_defaults(func=cmd_diag)

    p = sub.add_parser("etl", help="누적 DB 재구조화 작업(SFR-002)")
    p.add_argument("job", choices=["intervals", "status", "inactivity", "retention"])
    p.set_defaults(func=cmd_etl)

    p = sub.add_parser("dictionary", help="데이터 사전 생성(SFR-003)")
    p.add_argument("--out-dir", default="build")
    p.set_defaults(func=cmd_dictionary)

    sub.add_parser("ami-load", help="전력(AMI) 적재·통합(SFR-009)").set_defaults(func=cmd_ami_load)

    p = sub.add_parser("pseudo-run", help="가명처리 파이프라인(SFR-004)")
    p.add_argument("--include-memo", action="store_true", help="SFR-010 채택 시 자유기술 포함")
    p.add_argument("--record", help="가명처리 처리 기록(markdown) 출력 경로")
    p.set_defaults(func=cmd_pseudo_run)

    p = sub.add_parser("freetext-test", help="재식별 시험·추가검수(SFR-010)")
    p.add_argument("--out", help="재식별 시험 결과서 출력 경로")
    p.add_argument("--review-sheet", help="검수 시트(CSV) 출력 경로")
    p.add_argument("--review-record", help="추가검수 기록(markdown) 출력 경로")
    p.set_defaults(func=cmd_freetext_test)

    p = sub.add_parser("publish", help="전송용 DB 발행(SFR-006)")
    p.add_argument("--table", help="특정 테이블만(미지정 시 전체)")
    p.add_argument("--dry-run", action="store_true", help="실발행 없이 직렬화·이력만")
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("create-user", help="관리자 계정 생성(SFR-007)")
    p.add_argument("--username", required=True)
    p.add_argument("--role", choices=["viewer", "admin", "super_admin"], default="viewer")
    p.add_argument("--password", help="미지정 시 프롬프트 입력")
    p.set_defaults(func=cmd_create_user)

    p = sub.add_parser("gen-acl", help="Mosquitto ACL 생성(SFR-006)")
    p.add_argument("--out", default="deploy/mosquitto/config/acl")
    p.set_defaults(func=cmd_gen_acl)

    p = sub.add_parser("serve", help="대시보드·API 서버 실행(SFR-005)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
