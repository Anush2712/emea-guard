"""Downloadable risk reports."""
from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..services import reporting

router = APIRouter(tags=["reports"])


@router.get("/reports/risk-report.xlsx", summary="Multi-sheet Excel risk report (Pandas)")
def risk_xlsx(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return Response(reporting.excel_report(db), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="emea-guard-risk-report-{date.today()}.xlsx"'})


@router.get("/reports/gaps.csv", summary="All compliance gaps as CSV")
def gaps_csv(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return Response(reporting.gaps_csv(db), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="emea-guard-gaps-{date.today()}.csv"'})


@router.get("/reports/executive.html", response_class=HTMLResponse, summary="Executive report with Plotly charts")
def executive(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return HTMLResponse(reporting.html_report(db), headers={"Content-Disposition": f'attachment; filename="emea-guard-executive-report-{date.today()}.html"'})
