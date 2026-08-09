from PySide6.QtWidgets import QWidget,QVBoxLayout
from .widgets import EmptyStateWidget,quadrant_presentation
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
except ImportError:
    FigureCanvasQTAgg=None

class CompactChart(QWidget):
    def __init__(self,data,kind="bar"):
        super().__init__(); layout=QVBoxLayout(self)
        if not data or FigureCanvasQTAgg is None: layout.addWidget(EmptyStateWidget("No completed evaluations yet","analytics")); return
        figure=Figure(figsize=(4,2.2),tight_layout=True); figure.patch.set_alpha(0); ax=figure.add_subplot(111)
        labels=list(data); values=list(data.values())
        if kind=="donut":
            colors=[quadrant_presentation(x)[1] for x in labels]; labels=[quadrant_presentation(x)[0] for x in labels]
            ax.pie(values,labels=labels,colors=colors,wedgeprops={"width":.38,"edgecolor":"white"},textprops={"fontsize":7})
        else: ax.barh(labels,values,color="#2563EB"); ax.tick_params(labelsize=8); ax.spines[["top","right"]].set_visible(False)
        layout.addWidget(FigureCanvasQTAgg(figure))
