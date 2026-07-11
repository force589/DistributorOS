from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from textwrap import wrap

from distributoros.modules.invoices.repository import InvoiceDetails

A4_WIDTH = 595.28
A4_HEIGHT = 841.89
MARGIN = 42.0


@dataclass
class _Page:
    lines: list[str]


class InvoicePdfRenderer:
    """Small dependency-free PDF renderer for immutable invoice documents."""

    def render(self, details: InvoiceDetails) -> bytes:
        writer = _PdfWriter()
        layout = _InvoiceLayout(details)
        pages = layout.pages()
        for index, page in enumerate(pages, start=1):
            writer.add_page(page.lines, page_number=index, page_count=len(pages))
        return writer.render()


class _InvoiceLayout:
    def __init__(self, details: InvoiceDetails) -> None:
        self.details = details
        self.page = _Page(lines=[])
        self.pages_out: list[_Page] = []
        self.y = A4_HEIGHT - MARGIN

    def pages(self) -> list[_Page]:
        invoice = self.details.invoice
        self._header()
        self._section_title("Bill To")
        self._text(invoice.customer_name_snapshot, bold=True)
        for line in self._customer_lines():
            self._text(line)
        self._gap(12)
        self._section_title("Items")
        self._table_header()
        for item in self.details.items:
            product_lines = wrap(_clean(item.product_snapshot), width=28) or [""]
            row_height = max(18, 11 * len(product_lines) + 6)
            self._ensure_space(row_height + 4, repeat_table_header=True)
            start_y = self.y
            self._text_at(52, start_y, str(item.line_number), size=9)
            for offset, product_line in enumerate(product_lines):
                self._text_at(82, start_y - (offset * 11), product_line, size=9)
            self._text_at(282, start_y, _clean(item.unit_snapshot), size=9)
            self._text_at(
                346,
                start_y,
                _decimal_text(item.quantity_snapshot),
                size=9,
                align="right",
            )
            self._text_at(
                422,
                start_y,
                _money(item.unit_price_snapshot, self.details.invoice.currency),
                size=9,
                align="right",
            )
            self._text_at(
                540,
                start_y,
                _money(item.line_total, self.details.invoice.currency),
                size=9,
                align="right",
            )
            self.y -= row_height
            self._rule(light=True)
        self._totals()
        self._payment_summary()
        self._footer_note()
        self._finish_page()
        return self.pages_out

    def _header(self) -> None:
        invoice = self.details.invoice
        self._text(self.details.business_name, size=20, bold=True)
        self._text("DistributorOS Invoice", size=10)
        self._text_at(380, A4_HEIGHT - MARGIN, "INVOICE", size=22, bold=True)
        self._text_at(380, A4_HEIGHT - MARGIN - 24, invoice.invoice_number, size=12, bold=True)
        self._text_at(380, A4_HEIGHT - MARGIN - 42, f"Status: {invoice.status}", size=9)
        self._text_at(
            380,
            A4_HEIGHT - MARGIN - 58,
            f"Issue date: {invoice.issue_date.isoformat()}",
            size=9,
        )
        self._text_at(380, A4_HEIGHT - MARGIN - 74, f"Sale: {invoice.sale_number_snapshot}", size=9)
        self.y -= 92
        self._rule()

    def _customer_lines(self) -> list[str]:
        invoice = self.details.invoice
        lines = [
            invoice.customer_address_line_1_snapshot,
            invoice.customer_address_line_2_snapshot,
            _join_non_empty(
                [
                    invoice.customer_city_snapshot,
                    invoice.customer_state_snapshot,
                    invoice.customer_postal_code_snapshot,
                ]
            ),
            (
                f"Phone: {invoice.customer_phone_snapshot}"
                if invoice.customer_phone_snapshot
                else None
            ),
        ]
        return [line for line in lines if line]

    def _table_header(self) -> None:
        self._ensure_space(32)
        self._text_at(52, self.y, "#", size=9, bold=True)
        self._text_at(82, self.y, "Product", size=9, bold=True)
        self._text_at(282, self.y, "Unit", size=9, bold=True)
        self._text_at(346, self.y, "Qty", size=9, bold=True, align="right")
        self._text_at(422, self.y, "Rate", size=9, bold=True, align="right")
        self._text_at(540, self.y, "Line total", size=9, bold=True, align="right")
        self.y -= 12
        self._rule(light=True)

    def _totals(self) -> None:
        invoice = self.details.invoice
        self._ensure_space(76)
        self._amount_row("Subtotal", invoice.subtotal)
        self._amount_row("Tax", invoice.tax_total)
        self._amount_row("Grand total", invoice.grand_total, bold=True)

    def _payment_summary(self) -> None:
        self._ensure_space(96)
        self._section_title("Payment Summary")
        self._amount_row("Allocated payments", self.details.allocated_amount)
        self._amount_row("Outstanding balance", self.details.outstanding_amount, bold=True)
        if (
            self.details.outstanding_amount == Decimal("0.00")
            and self.details.invoice.status != "VOID"
        ):
            self._text("This invoice is fully covered by customer payments or credit.", size=9)
        elif self.details.invoice.status == "VOID":
            self._text(
                "This invoice is void. Financial reversal records are retained in the ledger.",
                size=9,
            )

    def _footer_note(self) -> None:
        self._ensure_space(48)
        self._gap(10)
        self._rule(light=True)
        self._text(
            f"Generated by DistributorOS. Amounts are shown in {self.details.invoice.currency}.",
            size=8,
        )

    def _amount_row(self, label: str, amount: Decimal, *, bold: bool = False) -> None:
        self._text_at(350, self.y, label, size=10, bold=bold)
        self._text_at(
            540,
            self.y,
            _money(amount, self.details.invoice.currency),
            size=10,
            bold=bold,
            align="right",
        )
        self.y -= 16

    def _section_title(self, value: str) -> None:
        self._ensure_space(24)
        self._gap(6)
        self._text(value, size=12, bold=True)

    def _text(self, value: str, *, size: int = 10, bold: bool = False) -> None:
        self._ensure_space(size + 6)
        self._text_at(MARGIN, self.y, value, size=size, bold=bold)
        self.y -= size + 4

    def _text_at(
        self,
        x: float,
        y: float,
        value: str,
        *,
        size: int = 10,
        bold: bool = False,
        align: str = "left",
    ) -> None:
        font = "F2" if bold else "F1"
        text = _clean(value)
        escaped = _escape_pdf_text(text)
        if align == "right":
            approx_width = len(text) * size * 0.48
            x -= approx_width
        self.page.lines.append(f"BT /{font} {size} Tf {x:.2f} {y:.2f} Td ({escaped}) Tj ET")

    def _rule(self, *, light: bool = False) -> None:
        width = "0.4" if light else "0.8"
        color = "0.75" if light else "0.25"
        self.page.lines.append(
            f"{color} G {width} w {MARGIN:.2f} {self.y:.2f} m "
            f"{(A4_WIDTH - MARGIN):.2f} {self.y:.2f} l S 0 G"
        )
        self.y -= 12

    def _gap(self, amount: float) -> None:
        self.y -= amount

    def _ensure_space(self, required: float, *, repeat_table_header: bool = False) -> None:
        if self.y - required < MARGIN + 34:
            self._finish_page()
            self.page = _Page(lines=[])
            self.y = A4_HEIGHT - MARGIN
            if repeat_table_header:
                self._table_header()

    def _finish_page(self) -> None:
        if self.page.lines:
            self.pages_out.append(self.page)


class _PdfWriter:
    def __init__(self) -> None:
        self.page_streams: list[str] = []

    def add_page(self, lines: list[str], *, page_number: int, page_count: int) -> None:
        footer = f"BT /F1 8 Tf {MARGIN:.2f} 24 Td (Page {page_number} of {page_count}) Tj ET"
        self.page_streams.append("\n".join([*lines, footer]))

    def render(self) -> bytes:
        objects: list[bytes] = []
        objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        page_count = len(self.page_streams)
        page_ids = [5 + index * 2 for index in range(page_count)]
        kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
        objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode())
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
        for index, stream in enumerate(self.page_streams):
            page_object_id = page_ids[index]
            stream_object_id = page_object_id + 1
            objects.append(
                (
                    "<< /Type /Page /Parent 2 0 R "
                    f"/MediaBox [0 0 {A4_WIDTH:.2f} {A4_HEIGHT:.2f}] "
                    "/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
                    f"/Contents {stream_object_id} 0 R >>"
                ).encode()
            )
            stream_bytes = stream.encode("latin-1", "replace")
            objects.append(
                b"<< /Length "
                + str(len(stream_bytes)).encode()
                + b" >>\nstream\n"
                + stream_bytes
                + b"\nendstream"
            )
        output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for index, body in enumerate(objects, start=1):
            offsets.append(len(output))
            output.extend(f"{index} 0 obj\n".encode())
            output.extend(body)
            output.extend(b"\nendobj\n")
        xref_at = len(output)
        output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
        output.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            output.extend(f"{offset:010d} 00000 n \n".encode())
        output.extend(
            (
                "trailer\n"
                f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
                "startxref\n"
                f"{xref_at}\n"
                "%%EOF\n"
            ).encode()
        )
        return bytes(output)


def _money(value: Decimal, currency: str) -> str:
    return f"{currency} {value.quantize(Decimal('0.01'))}"


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    return format(normalized, "f")


def _join_non_empty(values: list[str | None]) -> str | None:
    cleaned = [value for value in values if value]
    return ", ".join(cleaned) if cleaned else None


def _clean(value: str) -> str:
    return value.replace("\n", " ").replace("\r", " ")


def _escape_pdf_text(value: str) -> str:
    ascii_value = value.encode("latin-1", "replace").decode("latin-1")
    return ascii_value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
