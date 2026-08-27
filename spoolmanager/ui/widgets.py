"""Composants réutilisables : jauges, étiquettes, cartes de bobine et d'emplacement."""

from __future__ import annotations

from PySide6.QtCore import QMimeData, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QFontMetrics, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..models import STATE_LABELS, Spool
from . import theme

SPOOL_MIME = "application/x-spoolmanager-spool-id"


class FlowLayout(QLayout):
    """Disposition en grille fluide : les cartes se réorganisent selon la largeur."""

    def __init__(self, parent=None, margin=0, spacing=12):
        super().__init__(parent)
        self._items: list = []
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._layout(rect, apply=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _layout(self, rect, apply: bool) -> int:
        margins = self.contentsMargins()
        x = rect.x() + margins.left()
        y = rect.y() + margins.top()
        right = rect.right() - margins.right()
        line_height = 0

        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > right and line_height > 0:
                x = rect.x() + margins.left()
                y += line_height + self._spacing
                line_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._spacing
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + margins.bottom()


class Gauge(QWidget):
    """Barre de remplissage arrondie, teintée selon le niveau restant."""

    def __init__(self, parent=None, height: int = 8):
        super().__init__(parent)
        self._ratio = 0.0
        self._color = theme.SUCCESS
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_value(self, ratio: float, color: str) -> None:
        self._ratio = max(0.0, min(1.0, ratio))
        self._color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        radius = self.height() / 2

        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), radius, radius)
        painter.fillPath(path, QColor(theme.BORDER))

        filled = self.width() * self._ratio
        if filled > 0:
            clip = QPainterPath()
            clip.addRoundedRect(0, 0, max(filled, self.height()), self.height(), radius, radius)
            painter.fillPath(path.intersected(clip), QColor(self._color))
        painter.end()


class ColorDot(QWidget):
    """Pastille de la couleur réelle du filament."""

    def __init__(self, color: str = "#9E9E9E", size: int = 26, parent=None):
        super().__init__(parent)
        self._color = theme.safe_color(color)
        self.setFixedSize(size, size)

    def set_color(self, color: str) -> None:
        self._color = theme.safe_color(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(self._color))
        painter.setPen(QColor(theme.BORDER))
        painter.drawEllipse(1, 1, self.width() - 2, self.height() - 2)
        painter.end()


class Chip(QLabel):
    """Petite étiquette colorée : matière, état, emplacement."""

    def __init__(self, text: str, color: str = theme.MUTED, parent=None):
        super().__init__(text, parent)
        self.set_color(color)

    def set_color(self, color: str) -> None:
        # Qt lit un hexadécimal à huit chiffres comme #AARRGGBB, pas #RRGGBBAA :
        # la transparence doit passer par rgba() sous peine d'obtenir une autre teinte.
        rgb = QColor(color)
        tint = f"rgba({rgb.red()}, {rgb.green()}, {rgb.blue()}, 0.16)"
        edge = f"rgba({rgb.red()}, {rgb.green()}, {rgb.blue()}, 0.40)"
        self.setStyleSheet(
            f"background-color: {tint}; color: {color}; border: 1px solid {edge};"
            "border-radius: 6px; padding: 1px 7px; font-size: 11px; font-weight: 600;"
        )


class StatCard(QFrame):
    """Grand chiffre du tableau de bord."""

    def __init__(self, label: str, value: str = "-", accent: str = theme.TEXT, parent=None):
        super().__init__(parent)
        self.setProperty("role", "card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 13, 16, 13)
        layout.setSpacing(2)

        self._value = QLabel(value)
        self._value.setProperty("role", "stat")
        self._value.setStyleSheet(f"color: {accent};")
        self._caption = QLabel(label)
        self._caption.setProperty("role", "statLabel")

        layout.addWidget(self._value)
        layout.addWidget(self._caption)

    def set_value(self, value: str, caption: str | None = None) -> None:
        self._value.setText(value)
        if caption is not None:
            self._caption.setText(caption)


class SpoolCard(QFrame):
    """Carte d'une bobine sur l'étagère, déplaçable vers un emplacement."""

    clicked = Signal(int)
    activated = Signal(int)
    menu_requested = Signal(int, QPoint)

    def __init__(self, spool: Spool, low_threshold: float, parent=None):
        super().__init__(parent)
        self.spool = spool
        self._low_threshold = low_threshold
        self._selected = False
        self._press_position = QPoint()

        self.setProperty("role", "card")
        self.setFixedSize(304, 132)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: self.menu_requested.emit(self.spool.id, self.mapToGlobal(pos))
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(7)

        header = QHBoxLayout()
        header.setSpacing(9)
        self._dot = ColorDot(spool.color_hex)
        header.addWidget(self._dot)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        self._name = QLabel(spool.display_name)
        self._name.setStyleSheet("font-weight: 600; font-size: 13px;")
        self._subtitle = QLabel()
        self._subtitle.setProperty("role", "subtitle")
        self._subtitle.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        titles.addWidget(self._name)
        titles.addWidget(self._subtitle)
        header.addLayout(titles, 1)
        layout.addLayout(header)

        self._gauge = Gauge()
        layout.addWidget(self._gauge)

        footer = QHBoxLayout()
        footer.setSpacing(7)
        self._remaining = QLabel()
        self._remaining.setStyleSheet("font-size: 15px; font-weight: 700;")
        footer.addWidget(self._remaining)
        self._percent = QLabel()
        self._percent.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        footer.addWidget(self._percent)
        footer.addStretch(1)
        self._slot_chip = Chip("", theme.ACCENT)
        footer.addWidget(self._slot_chip)
        self._material = Chip("", theme.INFO)
        footer.addWidget(self._material)
        layout.addLayout(footer)

        self.refresh(spool, low_threshold)

    def refresh(self, spool: Spool, low_threshold: float) -> None:
        self.spool = spool
        self._low_threshold = low_threshold

        self._dot.set_color(spool.color_hex)

        details = [spool.filament_name]
        if spool.color_name:
            details.append(spool.color_name)
        if spool.shelf_location:
            details.append(f"case {spool.shelf_location}")
        details.append(STATE_LABELS.get(spool.state, spool.state))

        # La carte a une largeur fixe : les textes trop longs sont coupés proprement
        # plutôt que de déborder sur la pastille ou les étiquettes.
        available = self.width() - self._dot.width() - 37
        self._set_elided(self._name, spool.display_name, available)
        self._set_elided(self._subtitle, " · ".join(d for d in details if d), available)

        color = theme.level_color(spool.ratio, spool.remaining_g, low_threshold)
        self._gauge.set_value(spool.ratio, color)
        self._remaining.setText(f"{spool.remaining_g:.0f} g")
        self._remaining.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {color};")
        self._percent.setText(f"{spool.ratio * 100:.0f} % de {spool.initial_net_g:.0f} g")

        self._material.setText(spool.material or "?")
        if spool.loaded_slot:
            self._slot_chip.setText(f"Empl. {spool.loaded_slot}")
            self._slot_chip.show()
        else:
            self._slot_chip.hide()

        self.setToolTip(
            f"{spool.display_name}\n"
            f"{spool.remaining_g:.0f} g restants sur {spool.initial_net_g:.0f} g\n"
            f"Poids attendu sur la balance : {spool.gross_g:.0f} g\n"
            f"Valeur restante : {spool.value_eur:.2f} EUR"
        )

    @staticmethod
    def _set_elided(label: QLabel, text: str, width: int) -> None:
        metrics = QFontMetrics(label.font())
        label.setText(metrics.elidedText(text, Qt.ElideRight, max(40, width)))

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.setProperty("role", "cardSelected" if selected else "card")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_position = event.position().toPoint()
            self.clicked.emit(self.spool.id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.activated.emit(self.spool.id)
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if (event.position().toPoint() - self._press_position).manhattanLength() < 12:
            return

        mime = QMimeData()
        mime.setData(SPOOL_MIME, str(self.spool.id).encode())

        drag = QDrag(self)
        drag.setMimeData(mime)
        preview = QPixmap(self.size())
        preview.fill(Qt.transparent)
        self.render(preview)
        drag.setPixmap(preview)
        drag.setHotSpot(self._press_position)
        drag.exec(Qt.MoveAction)


def spool_id_from_mime(mime: QMimeData) -> int | None:
    if not mime.hasFormat(SPOOL_MIME):
        return None
    try:
        return int(bytes(mime.data(SPOOL_MIME)).decode())
    except ValueError:
        return None
