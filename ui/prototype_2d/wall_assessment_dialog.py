"""Qt editor and native quadrant plot for Assessment Area evaluations."""
from copy import deepcopy
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QComboBox,QDateEdit,QDialog,QDoubleSpinBox,QFormLayout,QHBoxLayout,QLabel,QLineEdit,QMessageBox,QPushButton,QTabWidget,QTableWidget,QTableWidgetItem,QTextEdit,QVBoxLayout,QWidget)
from prototype_2d.wall_assessment import (CONDITION, DESIGN, AssessmentCriterionResult,
 AssessmentMatrixTemplate, calculate_revision)

class QuadrantPlot(QWidget):
    def __init__(self,parent=None): super().__init__(parent); self.template=None; self.design=None; self.condition=None; self.setMinimumSize(420,300)
    def set_result(self,template,design,condition): self.template=template; self.design=design; self.condition=condition; self.setToolTip("" if design is None or condition is None else f"Design: {design:.3f}; Face: {condition:.3f}"); self.update()
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); r=QRectF(55,20,max(10,self.width()-75),max(10,self.height()-65)); t=self.template
        if not t: return
        x=t.face_condition_threshold; y=t.design_achievement_threshold; px=r.left()+x*r.width(); py=r.bottom()-y*r.height()
        p.fillRect(QRectF(r.left(),r.top(),px-r.left(),py-r.top()),QColor("#f6df72")); p.fillRect(QRectF(px,r.top(),r.right()-px,py-r.top()),QColor("#8bd17c")); p.fillRect(QRectF(r.left(),py,px-r.left(),r.bottom()-py),QColor("#ef7770")); p.fillRect(QRectF(px,py,r.right()-px,r.bottom()-py),QColor("#f2b764"))
        p.setPen(QPen(Qt.GlobalColor.black,1)); p.drawRect(r); p.drawLine(px,r.top(),px,r.bottom()); p.drawLine(r.left(),py,r.right(),py)
        p.drawText(QRectF(r.left(),r.top(),px-r.left(),py-r.top()),Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap,"Геометрия достигнута\nСостояние недостаточно"); p.drawText(QRectF(px,r.top(),r.right()-px,py-r.top()),Qt.AlignmentFlag.AlignCenter,"Хорошие\nрезультаты"); p.drawText(QRectF(r.left(),py,px-r.left(),r.bottom()-py),Qt.AlignmentFlag.AlignCenter,"Неприемлемо"); p.drawText(QRectF(px,py,r.right()-px,r.bottom()-py),Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap,"Состояние хорошее\nГеометрия неприемлема")
        p.drawText(r.left(),self.height()-10,"Face Condition Index →"); p.save(); p.translate(15,r.bottom()); p.rotate(-90); p.drawText(0,0,"Design Achievement Index →"); p.restore()
        if self.design is not None and self.condition is not None:
            cx=r.left()+self.condition*r.width(); cy=r.bottom()-self.design*r.height(); p.setBrush(QColor("#1261a0")); p.setPen(QPen(Qt.GlobalColor.white,2)); p.drawEllipse(QRectF(cx-7,cy-7,14,14))

class AssessmentAreaEvaluationDialog(QDialog):
    def __init__(self,area,evaluation,draft,save_callback,parent=None):
        super().__init__(parent); self.area=area; self.evaluation=evaluation; self.draft=deepcopy(draft); self.save_callback=save_callback; self.template=AssessmentMatrixTemplate.from_dict(draft.matrix_template_snapshot)
        self.setWindowTitle("Оценка борта"); self.resize(1050,720); root=QVBoxLayout(self); self.tabs=QTabWidget(); root.addWidget(self.tabs)
        self._general(); self._geometry(); self._condition(); self._matrix(); self._events(); self._history()
        buttons=QHBoxLayout(); buttons.addStretch(); draft_btn=QPushButton("Сохранить черновик"); done=QPushButton("Завершить оценку"); cancel=QPushButton("Отмена"); draft_btn.clicked.connect(lambda:self.save("draft")); done.clicked.connect(lambda:self.save("completed")); cancel.clicked.connect(self.reject)
        for b in (draft_btn,done,cancel): buttons.addWidget(b)
        root.addLayout(buttons); self.refresh()
    def _general(self):
        w=QWidget(); f=QFormLayout(w); self.date=QDateEdit(); self.date.setCalendarPopup(True); self.date.setDate(self.draft.assessment_date); self.inspector=QLineEdit(self.draft.inspector); self.detected=QLabel("Контурное бурение обнаружено по подтверждённой связи" if self.draft.controlled_blasting_present else "Подтверждённое контурное событие не найдено"); self.comments=QTextEdit(self.draft.comments); self.recommendations=QTextEdit(self.draft.recommendations)
        rev=next(r for r in self.area.geometry_revisions if r.id==self.draft.assessment_area_geometry_revision_id); f.addRow("Дата оценки",self.date); f.addRow("Инспектор",self.inspector); f.addRow("Assessment Area ID",QLabel(self.area.id)); f.addRow("Ревизия геометрии",QLabel(rev.id)); f.addRow("Отметки",QLabel(f"{rev.lower_elevation:g} — {rev.upper_elevation:g}")); f.addRow("Матрица",QLabel(self.template.id)); f.addRow("Обнаружение",self.detected); f.addRow("Комментарии",self.comments); f.addRow("Рекомендации",self.recommendations); self.tabs.addTab(w,"Общие")
    def spin(self,maxv=999): s=QDoubleSpinBox(); s.setRange(0,maxv); s.setDecimals(2); s.valueChanged.connect(self.refresh); return s
    def _geometry(self):
        w=QWidget(); f=QFormLayout(w); self.da=self.spin(90); self.aa=self.spin(90); self.db=self.spin(); self.ab=self.spin(); self.toe=self.spin(); self.method=QLineEdit(); self.measure_notes=QTextEdit()
        for label,widget in (("Проектный угол, °",self.da),("Фактический угол, °",self.aa),("Проектная берма, м",self.db),("Фактическая берма, м",self.ab),("Отклонение подошвы, м",self.toe),("Метод измерения",self.method),("Примечания",self.measure_notes)): f.addRow(label,widget)
        self.geometry_points=QLabel(); f.addRow("Баллы",self.geometry_points); self.tabs.addTab(w,"Геометрия")
    def _condition(self):
        w=QWidget(); self.condition_form=QFormLayout(w); self.controls={}
        for c in self.template.section(CONDITION).criteria:
            if c.kind in ("numeric","damage"):
                control=self.spin(100)
            else:
                control=QComboBox(); control.addItem("—",None)
                for o in c.options: control.addItem(o.label,o.id)
                control.currentIndexChanged.connect(self.refresh)
            self.controls[c.id]=control; self.condition_form.addRow(c.name,control)
        self.tabs.addTab(w,"Состояние борта")
    def _matrix(self):
        w=QWidget(); l=QVBoxLayout(w); tables=QHBoxLayout(); self.design_table=QTableWidget(); self.condition_table=QTableWidget()
        for table,title in ((self.design_table,"Результаты проектирования"),(self.condition_table,"Показатели состояния борта")):
            box=QVBoxLayout(); box.addWidget(QLabel(title)); table.setColumnCount(6); table.setHorizontalHeaderLabels(["Критерий","Наблюдение","Категория","Баллы","Макс.","Ручной"]); box.addWidget(table); tables.addLayout(box)
        l.addLayout(tables); self.summary=QLabel(); l.addWidget(self.summary); self.plot=QuadrantPlot(); l.addWidget(self.plot); self.tabs.addTab(w,"Матрица")
    def _events(self):
        table=QTableWidget(len(self.draft.linked_event_snapshots),4); table.setHorizontalHeaderLabels(["BlastEvent","Тип","Отметка","Ревизия карточки"])
        for row,e in enumerate(self.draft.linked_event_snapshots):
            for col,v in enumerate((e.blast_event_name,e.event_type,f"{e.event_elevation:g}",e.technical_card_revision_id or "—")): table.setItem(row,col,QTableWidgetItem(v))
        self.tabs.addTab(table,"Связанные события")
    def _history(self):
        table=QTableWidget(len(self.evaluation.revisions),7); table.setHorizontalHeaderLabels(["№","Дата","Статус","Геометрия","Матрица","Design","Condition"])
        for row,r in enumerate(self.evaluation.revisions):
            values=(r.revision_number,r.assessment_date or "—",r.status,r.assessment_area_geometry_revision_id,r.matrix_template_id,"—" if r.design_achievement_index is None else f"{r.design_achievement_index:.3f}","—" if r.face_condition_index is None else f"{r.face_condition_index:.3f}")
            for col,v in enumerate(values): table.setItem(row,col,QTableWidgetItem(str(v)))
        self.tabs.addTab(table,"История")
    def collect(self):
        d=self.draft; d.assessment_date=self.date.date().toPython(); d.inspector=self.inspector.text(); d.comments=self.comments.toPlainText(); d.recommendations=self.recommendations.toPlainText(); short=max(self.da.value()-self.aa.value(),0); deficit=max(self.db.value()-self.ab.value(),0); d.design_inputs={"design_bench_face_angle_deg":self.da.value(),"actual_bench_face_angle_deg":self.aa.value(),"bench_angle_shortfall_deg":short,"design_berm_width_m":self.db.value(),"actual_berm_width_m":self.ab.value(),"berm_width_deficit_m":deficit,"toe_offset_from_design_m":abs(self.toe.value()),"measurement_method":self.method.text(),"measurement_notes":self.measure_notes.toPlainText()}
        results=[]
        vals={"bench_angle":short,"berm_width":deficit,"toe_position":abs(self.toe.value())}
        for c in self.template.section(DESIGN).criteria: results.append(AssessmentCriterionResult(c.id,c.name,c.section,raw_numeric_value=vals[c.id],maximum_score=c.maximum_score))
        for c in self.template.section(CONDITION).criteria:
            control=self.controls[c.id]; numeric=control.value() if isinstance(control,QDoubleSpinBox) else None; option=control.currentData() if isinstance(control,QComboBox) else None
            results.append(AssessmentCriterionResult(c.id,c.name,c.section,raw_numeric_value=numeric,selected_option_id=option,maximum_score=c.maximum_score))
        d.criterion_results=results; calculate_revision(d); return d
    def refresh(self):
        if not hasattr(self,"summary"): return
        try: d=self.collect()
        except ValueError as e: self.summary.setText(str(e)); return
        for table,section in ((self.design_table,DESIGN),(self.condition_table,CONDITION)):
            rows=[r for r in d.criterion_results if r.section==section]; table.setRowCount(len(rows))
            for i,r in enumerate(rows):
                for j,v in enumerate((r.criterion_name_snapshot,r.raw_numeric_value if r.raw_numeric_value is not None else "—",r.selected_option_id or "—",r.accepted_score if r.accepted_score is not None else "—",r.maximum_score,"Да" if r.is_manual_override else "Нет")): table.setItem(i,j,QTableWidgetItem(str(v)))
        self.geometry_points.setText(" / ".join(f"{r.criterion_name_snapshot}: {r.accepted_score:g}" for r in d.criterion_results if r.section==DESIGN and r.accepted_score is not None)); self.summary.setText(f"Design: {d.design_achievement_points if d.design_achievement_points is not None else '—'} / 100; индекс: {d.design_achievement_index if d.design_achievement_index is not None else '—'}\nCondition: {d.face_condition_points if d.face_condition_points is not None else '—'} / 100; индекс: {d.face_condition_index if d.face_condition_index is not None else '—'}\n{d.result_label or 'Итог появится после заполнения критериев'}"); self.plot.set_result(self.template,d.design_achievement_index,d.face_condition_index)
    def save(self,status):
        try: self.collect(); self.save_callback(self.evaluation,self.draft,status); self.accept()
        except ValueError as e: QMessageBox.warning(self,"Не удалось сохранить",str(e))
