"""Slime House Friendly Animator v0.43.0: independent creature animation workshop."""
import sys
import math
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageSequence
from PySide6.QtCore import Qt, QTimer, Signal, QSettings, QThread, QStandardPaths
from PySide6.QtGui import QImage, QPixmap, QIcon, QPainter, QPen, QColor, QCursor
from pathlib import Path
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QSplitter,QLabel,
 QPushButton,QListWidget,QComboBox,QSpinBox,QFormLayout,QFileDialog,QMessageBox,QScrollArea,QCheckBox, QSlider, QTabBar, QMenu, QInputDialog, QColorDialog)
from studio.release_config import APP_VERSION, UPDATE_MANIFEST_URL, UPDATE_PUBLIC_KEY_B64
from studio.update_manager import check_update, download_verified_installer
from studio.resource_checks import bundled_resource_report
from studio.canvas_navigation import geometry as canvas_geometry, zoom_at
from studio.timeline_tools import timeline_summary, onion_composite
from studio.pet_suite_model import PetSuiteModel
from studio.edit_history import EditHistory
from studio.slimer_tool import SlimerSelection
from studio.pet_suite_templates import TEMPLATES
from studio.comparison_sync import comparison_position
from studio.playback_clock import PlaybackClock
from studio.playback_resume import resume_position
from studio.timeline_retime import retime_elapsed
from studio.slime_buddy import STATIONS, station_guide
from studio.technical_checks import check_animation
from studio.workspace_identity import animation_key
from studio.recovery import (recovery_path, read_recovery, discard_recovery,
    list_project_recoveries, write_project_recovery, discard_project_recovery)

def pixmap(img,size=260):
    rgba=img.convert('RGBA');data=rgba.tobytes('raw','RGBA')
    q=QImage(data,rgba.width,rgba.height,rgba.width*4,QImage.Format.Format_RGBA8888).copy()
    return QPixmap.fromImage(q).scaled(size,size,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.FastTransformation)

class SlimerColorTabs(QTabBar):
    """Named selection tabs with the small compatibility API of the old picker."""
    currentTextChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setExpanding(False)
        self.setUsesScrollButtons(True)
        self.currentChanged.connect(self._emit_current_text)

    def _emit_current_text(self, index):
        if index >= 0:
            self.currentTextChanged.emit(self.tabText(index))

    def addItem(self, name):
        return self.addTab(name)

    def addItems(self, names):
        for name in names:
            self.addItem(name)

    def currentText(self):
        index = self.currentIndex()
        return self.tabText(index) if index >= 0 else ''

    def setCurrentText(self, name):
        for index in range(self.count()):
            if self.tabText(index) == name:
                self.setCurrentIndex(index)
                return
        raise ValueError(f'Unknown Slimer selection tab: {name}')


class DragCanvas(QLabel):
    """Pixel-space hit testing with movable parts and bottom-right resize handles."""
    moved=Signal(int,int)
    resized=Signal(int,int)
    picked=Signal(int)
    anchor_chosen=Signal(int,int)
    angle_chosen=Signal(float)
    view_changed=Signal()
    cleaner_stroke=Signal(int,int)
    cleaner_stroke_start=Signal()
    slimer_stroke=Signal(int,int,bool)
    slimer_stroke_start=Signal()
    slimer_drag=Signal(int,int,str)
    slimer_drag_start=Signal()
    slimer_drag_end=Signal()
    def __init__(self):
        super().__init__();self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True);self._last=None;self._image_size=(128,128)
        self.parts=[];self.selected=-1;self._action=None;self.anchor_mode=False;self.anchors={};self.angles={}
        self.zoom=1.0;self.pan_x=0.0;self.pan_y=0.0;self._pan_last=None;self._art=None;self.slimer_active=False;self.cleaner_active=False;self._cleaner_painting=False;self._slimer_painting=False;self.slimer_transform_mode=False;self._slimer_last=None;self.slimer_bounds=None;self._slimer_handle=None
    def _geometry(self):
        return canvas_geometry(self.width(),self.height(),*self._image_size,self.zoom,self.pan_x,self.pan_y)
    def _pixel(self,pos):
        scale,ox,oy=self._geometry()
        return ((pos.x()-ox)/scale,(pos.y()-oy)/scale)
    def set_art(self,pixmap):
        self._art=pixmap
        self.update()
    def paintEvent(self,event):
        if self._art is None:return
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,False)
        scale,ox,oy=self._geometry()
        painter.drawPixmap(round(ox),round(oy),max(1,round(self._image_size[0]*scale)),max(1,round(self._image_size[1]*scale)),self._art)
        if self.slimer_active and self.slimer_bounds is not None:
            x0,y0,x1,y1=self.slimer_bounds
            left=ox+x0*scale;top=oy+y0*scale
            width=max(1,(x1-x0)*scale);height=max(1,(y1-y0)*scale)
            painter.setPen(QPen(QColor('#b5ff8d'),2,Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(round(left),round(top),round(width),round(height))
            if self.slimer_transform_mode:
                # Square resize handle and round rotation handle stay visible at any zoom.
                painter.setPen(QPen(QColor('#172d24'),2))
                painter.setBrush(QColor('#aaff80'))
                painter.drawRect(round(left+width-5),round(top+height-5),10,10)
                painter.setBrush(QColor('#75c9ff'))
                painter.drawEllipse(round(left+width/2-5),round(top-25),10,10)
                painter.setPen(QPen(QColor('#75c9ff'),2))
                painter.drawLine(round(left+width/2),round(top-15),round(left+width/2),round(top))
        painter.end()
    def _slimer_hit_handle(self,pos):
        if not self.slimer_bounds:return None
        scale,ox,oy=self._geometry()
        x0,y0,x1,y1=self.slimer_bounds
        x=pos.x();y=pos.y();right=ox+x1*scale;bottom=oy+y1*scale
        mid=ox+(x0+x1)*scale/2;top=oy+y0*scale
        if abs(x-mid)<=12 and abs(y-(top-20))<=12:return 'rotate'
        if abs(x-right)<=12 and abs(y-bottom)<=12:return 'scale'
        return None
    def wheelEvent(self,event):
        # Zoom around the pointer so the artwork beneath it stays in place.
        steps=event.angleDelta().y()/120
        if not steps:return
        self.zoom,self.pan_x,self.pan_y=zoom_at(self.width(),self.height(),*self._image_size,self.zoom,self.pan_x,self.pan_y,event.position().x(),event.position().y(),steps)
        self.update();self.view_changed.emit();event.accept()
    def reset_view(self):
        self.zoom=1.0;self.pan_x=0.0;self.pan_y=0.0
        self.update();self.view_changed.emit()
    def mousePressEvent(self,event):
        if self.cleaner_active and event.button()==Qt.MouseButton.LeftButton and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            x,y=self._pixel(event.position())
            self._cleaner_painting=True
            self.cleaner_stroke_start.emit()
            self.cleaner_stroke.emit(int(x),int(y))
            event.accept();return
        if self.slimer_active and event.button() in (Qt.MouseButton.LeftButton,Qt.MouseButton.RightButton) and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            x,y=self._pixel(event.position())
            if self.slimer_transform_mode and event.button()==Qt.MouseButton.LeftButton:
                self._slimer_last=(x,y);self._slimer_handle=self._slimer_hit_handle(event.position());self.slimer_drag_start.emit();event.accept();return
            self._slimer_painting=True;self._slimer_erase=event.button()==Qt.MouseButton.RightButton
            self.slimer_stroke_start.emit()
            self.slimer_stroke.emit(int(x),int(y),self._slimer_erase);event.accept();return
        if event.button()==Qt.MouseButton.MiddleButton or (event.button()==Qt.MouseButton.LeftButton and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self._pan_last=event.position();event.accept();return
        if event.button()==Qt.MouseButton.LeftButton:
            x,y=self._pixel(event.position());self._last=(x,y);self._action=None
            if self.anchor_mode and 0<=self.selected<len(self.parts):
                p=self.parts[self.selected]
                self.anchor_chosen.emit(round(x-p["x"]),round(y-p["y"]))
                self._last=None
                return
            if 0<=self.selected<len(self.parts):
                p=self.parts[self.selected]
                ax,ay=self.anchors.get(self.selected,[p['image'].width//2,p['image'].height//2])
                pivot=(p['x']+ax,p['y']+ay)
                theta=math.radians(self.angles.get(self.selected,0))
                radius=max(14,round(max(p['image'].width,p['image'].height)*0.65))
                handle=(pivot[0]+radius*math.cos(theta-math.pi/2),pivot[1]+radius*math.sin(theta-math.pi/2))
                if math.hypot(x-handle[0],y-handle[1])<=5:
                    self._action='rotate';return
                right=p['x']+p['image'].width;bottom=p['y']+p['image'].height
                if abs(x-right)<=4 and abs(y-bottom)<=4:self._action='resize'
            if not self._action:
                for i in reversed(range(len(self.parts))):
                    p=self.parts[i]
                    if p.get('visible',True) and p['x']<=x<p['x']+p['image'].width and p['y']<=y<p['y']+p['image'].height:
                        self.picked.emit(i);self._action='move';break
            if not self._action:self._last=None
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self._cleaner_painting:
            x,y=self._pixel(event.position())
            self.cleaner_stroke.emit(int(x),int(y))
            event.accept();return
        if self.slimer_active and self._slimer_last is not None:
            x,y=self._pixel(event.position());dx=round(x-self._slimer_last[0]);dy=round(y-self._slimer_last[1])
            if dx or dy:
                mode=self._slimer_handle or ('rotate' if event.modifiers() & Qt.KeyboardModifier.AltModifier else ('scale' if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 'move'))
                self.slimer_drag.emit(dx,dy,mode)
                self._slimer_last=(self._slimer_last[0]+dx,self._slimer_last[1]+dy)
            event.accept();return
        if self._slimer_painting:
            x,y=self._pixel(event.position());self.slimer_stroke.emit(int(x),int(y),self._slimer_erase);event.accept();return
        if self._pan_last is not None:
            delta=event.position()-self._pan_last
            self.pan_x+=delta.x();self.pan_y+=delta.y();self._pan_last=event.position()
            self.update();self.view_changed.emit();event.accept();return
        if self._last is not None and self._action:
            x,y=self._pixel(event.position());dx=round(x-self._last[0]);dy=round(y-self._last[1])
            if self._action=='rotate':
                p=self.parts[self.selected]
                ax,ay=self.anchors.get(self.selected,[p['image'].width//2,p['image'].height//2])
                angle=math.degrees(math.atan2(y-(p['y']+ay),x-(p['x']+ax)))+90
                self.angle_chosen.emit(round(angle)%360)
                return
            if dx or dy:
                if self._action=='resize':self.resized.emit(dx,dy)
                else:self.moved.emit(dx,dy)
                self._last=(self._last[0]+dx,self._last[1]+dy)
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        self._last=None;self._action=None;self._pan_last=None;self._slimer_painting=False;self._cleaner_painting=False;self._slimer_last=None;self._slimer_handle=None;self.slimer_drag_end.emit();super().mouseReleaseEvent(event)

class UpdateCheckWorker(QThread):
    result = Signal(object, str)
    def run(self):
        try:
            payload = check_update(APP_VERSION, UPDATE_MANIFEST_URL, UPDATE_PUBLIC_KEY_B64)
            self.result.emit(payload, '')
        except Exception as exc:
            self.result.emit(None, str(exc))

class UpdateDownloadWorker(QThread):
    result = Signal(object, str)
    def __init__(self, payload, destination, parent=None):
        super().__init__(parent)
        self.payload, self.destination = payload, destination
    def run(self):
        try:
            self.result.emit(str(download_verified_installer(self.payload, self.destination)), '')
        except Exception as exc:
            self.result.emit(None, str(exc))

class Suite(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle(f'Slime House Friendly Animator — v{APP_VERSION}');self.resize(1380,850)
        self._shs_edit=None;self.model=PetSuiteModel();self.selected=-1;self.frame=0;self.playframe=0;self.history=EditHistory();self._project_histories={0:self.history};self.advanced=False;self._loading_pose=False;self._pose_draft_key=None;self._pose_draft_dirty=False;self._workspace_frames={};self._workspace_tab_keys=[];self._switching_tab=False;self._active_workspace=None;self._project_name="Untitled Creature";self.settings=QSettings("SlimeHouse", "FriendlyAnimator");self._projects={};self._project_id=0;self._active_project_id=0;self._project_paths={};self._projects[0]=self.model;self._project_labels={0:self._project_name};self._project_frames={0:{}};self._project_views={0:(1.0,0.0,0.0)};self._project_selected={0:-1};self._project_animation={0:next(iter(TEMPLATES))};self._dirty_projects=set();self._saved_fingerprints={0:self.model.content_fingerprint()}
        geometry=self.settings.value("window_geometry",None)
        if geometry:self.restoreGeometry(geometry)
        QTimer.singleShot(0,self.ensure_window_visible)
        self.setStyleSheet('QWidget{background:#202a2b;color:#e4efe5;font-size:13px} QPushButton{background:#344c3e;border:1px solid #6e9d70;padding:8px;border-radius:5px} QPushButton:hover{background:#446b50} QPushButton:checked{background:#587f45;border:2px solid #b4ed70;color:#ffffff} QPushButton:disabled{color:#7f9288;border-color:#44554a} QListWidget,QComboBox,QSpinBox{background:#2b3835;border:1px solid #607c66;padding:5px} QLabel{background:transparent}')
        base=QWidget();self.setCentralWidget(base);outer=QVBoxLayout(base)
        top_container=QWidget();top=QHBoxLayout(top_container);top.setContentsMargins(0,0,0,0)
        top_scroll=QScrollArea();top_scroll.setWidget(top_container);top_scroll.setWidgetResizable(True);top_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded);top_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);top_scroll.setFixedHeight(42);outer.addWidget(top_scroll)
        for title,callback in [('Import PNG assets',self.import_assets),('Open creature',self.open_project),('New creature',self.new_project),('Save creature',self.save_project),('Export Sprite Sheet',self.export),('Export GIF / APNG',self.export_animated),('Export Frame PNG',self.export_current_frame),('Export All Frames',self.export_all_frames),('Edit Frame in SHS',self.edit_frame_in_shs),('Set SHS Location',self.choose_shs_location),('Reload SHS Edit',self.reload_shs_edit),('Replace Frame PNG',self.replace_current_frame_png)]:
            b=QPushButton(title);b.clicked.connect(callback);top.addWidget(b)
        update_button=QPushButton('Check for updates');update_button.clicked.connect(self.check_for_updates);top.addWidget(update_button)
        self.status=QLabel('Welcome! Import PNG parts, pick an animation, and create your first pose.');outer.addWidget(self.status)
        mode_container=QWidget();modebar=QHBoxLayout(mode_container);modebar.setContentsMargins(0,0,0,0)
        mode_scroll=QScrollArea();mode_scroll.setWidget(mode_container);mode_scroll.setWidgetResizable(True);mode_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded);mode_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);mode_scroll.setFixedHeight(42);outer.addWidget(mode_scroll)
        self.mode=QPushButton('Easy Mode 🌱  •  Switch to Advanced');self.mode.clicked.connect(self.toggle_mode);modebar.addWidget(self.mode)
        undo=QPushButton('↶ Undo');undo.clicked.connect(self.undo);modebar.addWidget(undo)
        redo=QPushButton('↷ Redo');redo.clicked.connect(self.redo);modebar.addWidget(redo)
        from PySide6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence('Ctrl+Z'),self,activated=self.undo)
        QShortcut(QKeySequence('Ctrl+Shift+Z'),self,activated=self.redo)
        QShortcut(QKeySequence('Ctrl+Y'),self,activated=self.redo)
        # App-wide brush sizing follows whichever painting tool is active.
        # ApplicationShortcut also works while focus is in the canvas or side panels.
        for key, delta in (('+', 1), ('=', 1), ('-', -1)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(lambda step=delta: self.adjust_active_brush_size(step))
        self.onion=QCheckBox('Ghost nearby poses');self.onion.setChecked(False);self.onion.setToolTip('Show faint neighboring poses to help you judge movement. Guides are never exported.');# Ghost controls are now located at the top of the left tool panel.
        self.onion_next=QCheckBox('Also show next');self.onion_next.setToolTip('Show the following pose as another faint guide.');self.onion_next.toggled.connect(self.refresh)
        self.onion.stateChanged.connect(self.refresh)
        modebar.addStretch(1)
        splitter=QSplitter(Qt.Orientation.Horizontal);outer.addWidget(splitter,1)
        left=QWidget();ll=QVBoxLayout(left);ll.setContentsMargins(5,4,5,4)
        ghost_row=QHBoxLayout();ghost_row.addWidget(self.onion);ghost_row.addWidget(self.onion_next);ll.addLayout(ghost_row)
        ll.addWidget(QLabel('ASSET LIBRARY'))
        self.assets=QListWidget();self.assets.currentRowChanged.connect(self.select_asset);ll.addWidget(self.assets,1)
        order=QHBoxLayout();ll.addLayout(order)
        for label,offset in [('Move layer up',1),('Move layer down',-1)]:
            b=QPushButton(label);b.clicked.connect(lambda checked=False,d=offset:self.move_layer(d));order.addWidget(b)
        self.active_asset_label=QLabel('Editing: No asset selected')
        self.active_asset_label.setToolTip('Choose a row in the Asset Library above. Only that asset receives sizing and placement edits.')
        ll.addWidget(self.active_asset_label)
        form=QFormLayout();ll.addLayout(form)
        self.x=QSpinBox();self.y=QSpinBox();self.w=QSpinBox();self.h=QSpinBox()
        for spin in (self.x,self.y,self.w,self.h):spin.setRange(-2048 if spin in (self.x,self.y) else 1,2048);spin.valueChanged.connect(self.update_asset)
        for label,spin in [('X',self.x),('Y',self.y),('Width (px)',self.w),('Height (px)',self.h)]:form.addRow(label,spin)
        self.lock=QCheckBox('Lock aspect ratio');self.lock.setChecked(True);ll.addWidget(self.lock)
        self.angle=QSpinBox();self.angle.setRange(-360,360);self.angle.setSuffix('°');self.angle.setToolTip('Turn this part around its yellow joint dot. Original pixels are preserved.');form.addRow('Turn part (degrees)',self.angle);self.angle.valueChanged.connect(self.turn_part)
        self.turn_tip=QLabel('🌱 Tip: place a yellow joint dot, then turn an arm, leg or tail around it.');self.turn_tip.setWordWrap(True);ll.addWidget(self.turn_tip)
        ll.addWidget(QLabel('Connect body parts • optional'))
        self.parent_picker=QComboBox();ll.addWidget(self.parent_picker)
        attach_buttons=QHBoxLayout();ll.addLayout(attach_buttons)
        connect=QPushButton('🔗 Connect selected part');connect.setToolTip('Keep this part attached when its parent moves.');connect.clicked.connect(self.connect_part);attach_buttons.addWidget(connect)
        disconnect=QPushButton('Unlink');disconnect.clicked.connect(self.disconnect_part);attach_buttons.addWidget(disconnect)
        self.anchor_button=QPushButton('📍 Place a joint dot')
        self.anchor_button.setCheckable(True)
        self.anchor_button.setToolTip('Select a part, click here, then click where it bends or connects on the canvas. Click again to exit.')
        self.anchor_button.toggled.connect(self.toggle_anchor_mode)
        ll.addWidget(self.anchor_button)
        self.joint_tip=QLabel('Joint dots help you see where parts connect. Optional!')
        self.joint_tip.setWordWrap(True);ll.addWidget(self.joint_tip)
        ll.addWidget(QLabel('QUICK FIXES • selected part'))
        quick=QHBoxLayout();ll.addLayout(quick)
        for label,axis in [('↔ Flip left/right','horizontal'),('↕ Flip up/down','vertical')]:
            b=QPushButton(label);b.setToolTip('Mirror the selected part. Undo restores it.');b.clicked.connect(lambda checked=False,a=axis:self.flip_selected(a));quick.addWidget(b)
        alignment=QHBoxLayout();ll.addLayout(alignment)
        for label,axis in [('Center ↔','horizontal'),('Center ↕','vertical'),('Center both','both')]:
            b=QPushButton(label);b.setToolTip('Move the selected part to the middle of the canvas on this axis.');b.clicked.connect(lambda checked=False,a=axis:self.center_selected(a));alignment.addWidget(b)
        self.reset=QPushButton('↺ Restore original size');self.reset.setToolTip('Restore the PNG’s imported width and height in one undoable step.');self.reset.clicked.connect(self.reset_size);ll.addWidget(self.reset)
        self.advanced_label=QLabel('Advanced tools: exact X/Y coordinates and frame editing')
        ll.addWidget(self.advanced_label)
        ll.addWidget(QLabel('🟢 SLIMER TOOL • select pixels, then place'))
        self.slimer_toggle=QPushButton('Activate Slimer Tool');self.slimer_toggle.setCheckable(True);self.slimer_toggle.toggled.connect(self.slimer_toggle_mode);ll.addWidget(self.slimer_toggle)
        self.slimer_drag_toggle=QPushButton('Drag selected pixels (Shift=resize, Alt=rotate)')
        self.slimer_drag_toggle.setCheckable(True)
        self.slimer_drag_toggle.setToolTip('First highlight pixels, then click Finish Selecting. Drag the outlined selection to move it; Shift-drag resizes and Alt-drag rotates. Click Edit Selection to paint more highlights.')
        self.slimer_drag_toggle.toggled.connect(self.slimer_drag_mode)
        ll.addWidget(self.slimer_drag_toggle)
        self.slimer_finish=QPushButton('✓ Finish Selecting → Move')
        self.slimer_finish.setToolTip('Finish highlighting. Hide the colored paint and move the selected pixels with a clear outline. Use Edit Selection to adjust the mask.')
        self.slimer_finish.clicked.connect(self.slimer_finish_selecting)
        ll.addWidget(self.slimer_finish)
        self.slimer_selection_undo=[];self.slimer_selection_redo=[];self._slimer_numeric_replaying=False
        selection_actions=QHBoxLayout();ll.addLayout(selection_actions)
        for label,callback in [('Slimer Undo',self.slimer_undo_selection),('Slimer Redo',self.slimer_redo_selection)]:
            b=QPushButton(label);b.clicked.connect(callback);selection_actions.addWidget(b)
        ll.addWidget(QLabel('SLIME CLEANER • erase pixels to transparency'))
        self.cleaner_toggle=QPushButton('Activate Slime Cleaner')
        self.cleaner_toggle.setCheckable(True)
        self.cleaner_toggle.setToolTip('Independent eraser. Left-drag to clear pixels on the current pose. Undo restores a stroke.')
        self.cleaner_toggle.toggled.connect(self.cleaner_toggle_mode)
        ll.addWidget(self.cleaner_toggle)
        self.cleaner_brush=QSpinBox();self.cleaner_brush.setRange(1,32);self.cleaner_brush.setValue(1)
        self.cleaner_brush.setToolTip('While Slime Cleaner is active, press + or = to increase size and - to decrease it.');form.addRow('Cleaner brush size (+ / -)',self.cleaner_brush)
        self.slimer_brush=QSpinBox();self.slimer_brush.setRange(1,32);self.slimer_brush.setValue(1);self.slimer_brush.setToolTip('While Slimer is active, press + or = to increase highlight size and - to decrease it.');form.addRow('Slimer brush size (+ / -)',self.slimer_brush)
        self.slimer_dx=QSpinBox();self.slimer_dy=QSpinBox();self.slimer_turn=QSpinBox();self.slimer_scale=QSpinBox()
        for spin in (self.slimer_dx,self.slimer_dy):spin.setRange(-2048,2048)
        self.slimer_turn.setRange(-360,360);self.slimer_scale.setRange(10,800);self.slimer_scale.setValue(100)
        for label,spin in [('Slime move X',self.slimer_dx),('Slime move Y',self.slimer_dy),('Slime rotate °',self.slimer_turn),('Slime size %',self.slimer_scale)]:form.addRow(label,spin)
        for spin in (self.slimer_dx,self.slimer_dy,self.slimer_turn,self.slimer_scale):
            spin.valueChanged.connect(lambda value, control=spin: self.slimer_numeric_changed(control, value))
            spin.setToolTip('Slimer numeric adjustment. Slimer Undo reverses this change without changing placed artwork.')
        self.slimer_move_original=QCheckBox('Move Original Pixels (uncheck to Copy Pixels)')
        self.slimer_move_original.setChecked(True)
        self.slimer_move_original.setToolTip('Checked: clear selected pixels from the active pose when placing. Unchecked: copy them and keep the originals. Existing saved poses stay unchanged.')
        ll.addWidget(self.slimer_move_original)
        self.slimer_preview_label=QLabel('Finish Selecting to show preview')
        self.slimer_preview_label.setMinimumHeight(142)
        self.slimer_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.slimer_preview_label.setStyleSheet('background: #202833; border: 1px solid #64748b;')
        self.slimer_preview_label.setToolTip('Preview of selected pixels and their current move, rotation, and scale. Not exported.')
        slimer_actions=QHBoxLayout();ll.addLayout(slimer_actions)
        for label,callback in [('Place as Layer',self.slimer_place_layer),('Place Frame',self.slimer_place_frame),('Clear Selection',self.slimer_clear)]:
            button=QPushButton(label);button.clicked.connect(callback);slimer_actions.addWidget(button)
        self.slimer_confirm_all=QPushButton('✓ Confirm All Placements')
        self.slimer_confirm_all.setToolTip('Place all color-tab selections together as one undoable layer. Each tab keeps its own movement, rotation and size. For one tab, use Place as Layer or Place Frame.')
        self.slimer_confirm_all.clicked.connect(self.slimer_confirm_all_placements)
        ll.addWidget(self.slimer_confirm_all)
        # Independent, color-coded selection masks for animation phases.
        # The color is a canvas overlay only; exports never include it.
        self.slimer_phase_colors={'Start':'#54e88a','Middle':'#58b9ff','End':'#d38bff'}
        self.slimer_phase_masks={}
        self.slimer_phase_transforms={}  # Each highlight phase owns its own move/rotate/scale.
        self.slimer_phase_histories={}  # Undo/Redo stays with its color tab.
        self.slimer_phase_picker=SlimerColorTabs()
        self.slimer_phase_picker.addItems(self.slimer_phase_colors)
        self.slimer_phase_picker.setToolTip('Click a color tab to edit its independent pixel selection and transform. Tabs scroll when many colors are used.')
        self.slimer_phase_picker.currentTextChanged.connect(self.slimer_switch_phase)
        form.addRow('Selection color tabs',self.slimer_phase_picker)
        phase_buttons=QHBoxLayout();ll.addLayout(phase_buttons)
        self.slimer_color_button=QPushButton('Change highlight color')
        color_button=self.slimer_color_button
        color_button.clicked.connect(self.slimer_choose_color)
        phase_buttons.addWidget(color_button)
        add_phase=QPushButton('+ New phase')
        add_phase.clicked.connect(self.slimer_add_phase)
        phase_buttons.addWidget(add_phase)
        self.slimer_selection=None
        self._update_slimer_color_button()

        splitter.addWidget(self.scroll_panel(left))
        middle=QWidget();ml=QVBoxLayout(middle);ml.setContentsMargins(5,2,5,3);ml.setSpacing(3)
        self.choose_toggle=QPushButton('▾ Choose Animation')
        self.choose_toggle.setCheckable(True);self.choose_toggle.setChecked(self.settings.value('choose_open',True,type=bool))
        ml.addWidget(self.choose_toggle)
        self.anim=QComboBox();self.anim.addItems(TEMPLATES);self.anim.currentTextChanged.connect(self.change_anim);ml.addWidget(self.anim)
        self.recipe_toggle=QPushButton('▾ Follow Recipe')
        self.recipe_toggle.setCheckable(True);self.recipe_toggle.setChecked(self.settings.value('recipe_open',True,type=bool))
        # Legacy recipe controls retained internally for timeline compatibility, but removed from the workspace.
        self.recipe_toggle.setChecked(False)
        self.recipe_toggle.hide()
        self.steps=QListWidget();self.steps.setMaximumHeight(105);self.steps.currentRowChanged.connect(self.select_step);ml.addWidget(self.steps)
        self.instruction=QLabel();self.instruction.setWordWrap(True);ml.addWidget(self.instruction)
        self.choose_toggle.toggled.connect(lambda on:(self.anim.setVisible(on),self.settings.setValue('choose_open',on)))
        self.recipe_toggle.toggled.connect(lambda on:(self.steps.setVisible(on),self.instruction.setVisible(on),self.settings.setValue('recipe_open',on)))
        self.anim.setVisible(self.choose_toggle.isChecked())
        self.steps.hide();self.instruction.hide()
        self.buddy_toggle=QCheckBox('🌱 Slime Buddy ON / OFF');self.buddy_toggle.setChecked(self.settings.value('slime_buddy_enabled',True,type=bool));self.buddy_toggle.setToolTip('Turn all optional Slime Buddy guidance on or off. Your editing tools still work.');ml.addWidget(self.buddy_toggle)
        buddy_row=QHBoxLayout();ml.addLayout(buddy_row)
        self.buddy_station=QComboBox();self.buddy_station.addItems(STATIONS);self.buddy_station.setToolTip('Choose the station you want help with. This never edits your art.');buddy_row.addWidget(self.buddy_station)
        self.buddy_details=QLabel();self.buddy_details.setWordWrap(True);self.buddy_details.setStyleSheet('color:#c7e9c6;padding:4px');ml.addWidget(self.buddy_details)
        self.pose_tip=QLabel();self.pose_tip.setWordWrap(True);self.pose_tip.setStyleSheet('color:#bce6b9;padding:3px');ml.addWidget(self.pose_tip)
        self.slimer_buddy_tip=QLabel('🟢 Slime Buddy • Pick a color tab and highlight pixels. Click Finish Selecting to move the outlined selection; use Edit Selection to highlight more. Place as Layer or Place Frame for one selection, or Confirm All Placements for multiple tabs. Highlights are never exported.')
        self.slimer_buddy_tip.setWordWrap(True)
        self.slimer_buddy_tip.setStyleSheet('color:#c7e9c6;background:#30483b;border:1px solid #64866b;border-radius:6px;padding:8px')
        self.slimer_buddy_tip.setToolTip('This tip is optional and appears only while Slime Buddy and Slimer Tool are enabled.')
        # Slime Buddy guidance lives in the comparison dock, not above the canvas.
        self.check_button=QPushButton('✓ Check animation readiness');self.check_button.setToolTip('Optional technical checks only. Never judges your artwork.');self.check_button.clicked.connect(self.show_technical_checks);ml.addWidget(self.check_button)
        self.buddy_station.currentTextChanged.connect(self.refresh_buddy)
        self.buddy_toggle.toggled.connect(self.refresh_buddy)
        self.buddy_toggle.toggled.connect(lambda enabled:self.settings.setValue("slime_buddy_enabled",enabled))
        self.refresh_buddy()
        ml.addWidget(QLabel('STEP 2 • BUILD YOUR POSE — DRAG PARTS ON THE CANVAS'))
        self.canvas=DragCanvas();self.canvas.cleaner_stroke.connect(self.cleaner_paint);self.canvas.cleaner_stroke_start.connect(self.cleaner_start_stroke);self.canvas.slimer_stroke.connect(self.slimer_paint);self.canvas.slimer_stroke_start.connect(self.slimer_start_stroke);self.canvas.slimer_drag.connect(self.slimer_drag_transform);self.canvas.slimer_drag_start.connect(self.slimer_start_transform);self.canvas.slimer_drag_end.connect(self.slimer_end_transform);self.canvas.moved.connect(self.drag_part);self.canvas.resized.connect(self.resize_drag);self.canvas.picked.connect(self.assets.setCurrentRow);self.canvas.anchor_chosen.connect(self.place_anchor);self.canvas.angle_chosen.connect(self.turn_part);self.canvas.setMinimumHeight(380);self.canvas.setStyleSheet('background:#303e3c;border:1px solid #64866b');ml.addWidget(self.canvas,1);self.canvas.setToolTip('Click a part to select. Drag to move, use the green corner to resize, or drag the blue circle to turn.')
        nav=QHBoxLayout();ml.addLayout(nav)
        nav.addWidget(QLabel('Canvas view:'))
        fit=QPushButton('Fit to Canvas');fit.setToolTip('Show the whole creature again (does not resize your artwork).');fit.clicked.connect(self.canvas.reset_view);nav.addWidget(fit)
        self.zoom_label=QLabel('100%');nav.addWidget(self.zoom_label)
        nav.addWidget(QLabel('Wheel: zoom  •  Middle-drag or Ctrl+drag: move view'))
        nav.addStretch(1)
        self.canvas.view_changed.connect(self.canvas_view_changed)
        # Workspace tabs sit immediately below the main canvas, aligned to the left.
        tabline=QHBoxLayout();tabline.setContentsMargins(0,0,0,0);ml.addLayout(tabline)
        self.workspace_tabs=QTabBar();self.workspace_tabs.setMovable(True);self.workspace_tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu);self.workspace_tabs.customContextMenuRequested.connect(self.workspace_tab_context_menu)
        self.workspace_tabs.setExpanding(False);self.workspace_tabs.setUsesScrollButtons(True)
        self.workspace_tabs.setToolTip('Switch between your creature, animations and work phases. Your current pose is remembered.')
        self.workspace_tabs.setStyleSheet('QTabBar::tab{padding:8px 12px;margin-right:3px;background:#30443a;border:1px solid #567b5c;border-radius:5px} QTabBar::tab:selected{background:#547c58;color:white;border-bottom:3px solid #a6df83}')
        self.workspace_tabs.currentChanged.connect(self.switch_workspace_tab)
        self.workspace_tabs.tabMoved.connect(self.workspace_tab_moved)
        tabline.addWidget(self.workspace_tabs,1)
        self.add_workspace=QPushButton('+');self.add_workspace.setFixedWidth(36)
        self.add_workspace.setToolTip('Open an animation or another work phase')
        self.add_workspace.clicked.connect(self.workspace_menu);tabline.addWidget(self.add_workspace)
        ml.addWidget(QLabel('POSE TIMELINE • click a picture to edit that pose'))
        self.timeline=QListWidget();self.timeline.setFlow(QListWidget.Flow.LeftToRight);self.timeline.setMaximumHeight(116);self.timeline.setIconSize(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(66,66));self.timeline.setSpacing(5);self.timeline.currentRowChanged.connect(self.load_frame);ml.addWidget(self.timeline)
        timing=QHBoxLayout();ml.addLayout(timing);timing.addWidget(QLabel('How long should this pose last?'))
        self.duration=QSpinBox();self.duration.setRange(40,2000);self.duration.setSingleStep(25);self.duration.setSuffix(' ms');self.duration.setValue(125)
        self.duration.setToolTip('Shorter means faster movement. Try 125 ms to start!')
        self.duration.valueChanged.connect(self.change_duration);timing.addWidget(self.duration);timing.addStretch(1)
        actions=QHBoxLayout();ml.addLayout(actions)
        for label,callback in [('Save Current Pose',self.save_frame),('Restore Previous Pose',self.restore_previous_timeline_pose),('Duplicate last frame',self.duplicate_frame),('Previous frame',self.prev_frame),('Next frame',self.next_frame)]:
            b=QPushButton(label);b.clicked.connect(callback);actions.addWidget(b)
        timeline_tools=QHBoxLayout();ml.addLayout(timeline_tools)
        for label,callback in [('➕ Add pose',self.insert_pose),('📥 Import Pose PNG',self.import_pose_png),('📋 Copy pose',self.copy_pose),('🗑 Remove pose',self.remove_pose),('← Shift pose',lambda:self.shift_pose(-1)),('Shift pose →',lambda:self.shift_pose(1))]:
            button=QPushButton(label);button.setToolTip('Edit the saved poses in this animation. You can undo this change.');button.clicked.connect(callback);timeline_tools.addWidget(button)
        splitter.addWidget(self.scroll_panel(middle))
        right=QWidget();rl=QVBoxLayout(right);rl.addWidget(QLabel('STEP 3 • COMPARE & PREVIEW'))
        buddy_line=QHBoxLayout();rl.addLayout(buddy_line)
        self.buddy_mascot=QLabel();self.buddy_mascot.setFixedSize(56,56)
        self.buddy_mascot.setPixmap(QPixmap(str(Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'studio'/'assets'/'slime_buddy_16bit.png')).scaled(56,56,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.FastTransformation))
        buddy_line.addWidget(self.buddy_mascot)
        self.buddy_bubble=QLabel('SLIME BUDDY\nTips for your tools!');self.buddy_bubble.setWordWrap(True)
        self.buddy_bubble.setStyleSheet('color:#171d18;background:#f7f7ee;border:3px solid #101510;padding:7px;font-family:monospace;font-weight:bold')
        buddy_line.addWidget(self.buddy_bubble,1)
        self.buddy_dock_toggle=QCheckBox('ON');self.buddy_dock_toggle.setChecked(self.buddy_toggle.isChecked())
        self.buddy_dock_toggle.setToolTip('Turn Slime Buddy guidance on or off. Preference is saved.')
        self.buddy_dock_toggle.toggled.connect(self.buddy_toggle.setChecked)
        self.buddy_toggle.toggled.connect(self.buddy_dock_toggle.setChecked)
        buddy_line.addWidget(self.buddy_dock_toggle)
        rl.addWidget(self.slimer_buddy_tip)

        # Preset 2D reference drawings and shape selector were intentionally removed.
        # User-uploaded references below remain available as an optional tool.
        rl.addWidget(QLabel('SLIMER PREVIEW • selected pixels only'))
        rl.addWidget(self.slimer_preview_label)
        # User-provided animation reference: separate from editing and never included in exports.
        self.reference_files=[]
        self.reference_index=0
        self.reference_timer=QTimer(self)
        self.reference_timer.timeout.connect(self.advance_uploaded_reference)
        self.uploaded_reference_toggle=QCheckBox('Show my animation reference')
        self.uploaded_reference_toggle.setChecked(False)
        rl.addWidget(self.uploaded_reference_toggle)
        self.uploaded_reference_panel=QWidget();upl=QVBoxLayout(self.uploaded_reference_panel)
        upload_buttons=QHBoxLayout();upl.addLayout(upload_buttons)
        for label,callback in [('Load PNG / GIF / APNG / sheet',self.load_uploaded_reference),('Clear',self.clear_uploaded_reference)]:
            b=QPushButton(label);b.clicked.connect(callback);upload_buttons.addWidget(b)
        self.uploaded_reference_image=QLabel('Load an image to use as a visual reference. Not exported.')
        self.uploaded_reference_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.uploaded_reference_image.setMinimumHeight(145)
        self.uploaded_reference_image.setStyleSheet('background:#303e3c')
        upl.addWidget(self.uploaded_reference_image)
        reference_controls=QHBoxLayout();upl.addLayout(reference_controls)
        self.reference_play=QPushButton('▶ Play');self.reference_play.setCheckable(True)
        self.reference_play.toggled.connect(self.toggle_uploaded_reference_play)
        for label,callback in [('◀',lambda:self.step_uploaded_reference(-1)),('▶',lambda:self.step_uploaded_reference(1))]:
            b=QPushButton(label);b.clicked.connect(callback);reference_controls.addWidget(b)
        reference_controls.addWidget(self.reference_play)
        self.reference_zoom=QSpinBox();self.reference_zoom.setRange(1,8);self.reference_zoom.setValue(2)
        self.reference_zoom.setPrefix('Zoom ');self.reference_zoom.setSuffix('×')
        self.reference_zoom.valueChanged.connect(self.render_uploaded_reference)
        reference_controls.addWidget(self.reference_zoom)
        self.reference_status=QLabel('No reference loaded');upl.addWidget(self.reference_status)
        rl.addWidget(self.uploaded_reference_panel)
        self.uploaded_reference_toggle.toggled.connect(self.uploaded_reference_panel.setVisible)
        self.uploaded_reference_panel.hide()
        rl.addWidget(QLabel('Your creature • frame preview'))
        preview_zoom_row=QHBoxLayout();rl.addLayout(preview_zoom_row)
        self.preview_zoom=150
        for text, action in [('−',-50),('+',50),('Fit',0)]:
            b=QPushButton(text);b.clicked.connect(lambda checked=False,step=action:self.change_preview_zoom(step));preview_zoom_row.addWidget(b)

        self.preview=QLabel();self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter);self.preview.setMinimumSize(150,150);self.preview.setStyleSheet('background:#303e3c')
        self.preview_scroll=QScrollArea();self.preview_scroll.setWidget(self.preview);self.preview_scroll.setWidgetResizable(False)
        self.preview_scroll.setMinimumHeight(175);rl.addWidget(self.preview_scroll)

        self.play=QPushButton('▶ Play your animation');self.play.setCheckable(True);rl.addWidget(self.play)
        self.play.toggled.connect(self.play_toggled)
        speed_row=QHBoxLayout();rl.addLayout(speed_row);speed_row.addWidget(QLabel('Playback speed'))
        self.speed=QComboBox();self.speed.addItem('Slow • ½×',0.5);self.speed.addItem('Normal • 1×',1.0);self.speed.addItem('Fast • 2×',2.0);self.speed.setCurrentIndex(1);speed_row.addWidget(self.speed)
        self.loop=QCheckBox('Repeat animation');self.loop.setChecked(True);rl.addWidget(self.loop)
        self.loop.toggled.connect(self.restart_playback)
        self.speed.currentIndexChanged.connect(self.restart_playback)
        rl.addStretch(1);splitter.addWidget(self.scroll_panel(right))
        self.main_splitter=splitter
        self.comparison_panel=splitter.widget(2)
        self.comparison_toggle=QPushButton('👁 Hide comparison')
        self.comparison_toggle.setToolTip('Give the canvas more room. Click again to bring back the comparison.')
        self.comparison_toggle.clicked.connect(self.toggle_comparison)
        modebar.addWidget(self.comparison_toggle)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(7)
        saved=self.settings.value('splitter_sizes',None)
        if isinstance(saved,list) and len(saved)==3:
            try:splitter.setSizes([max(100,int(v)) for v in saved])
            except (ValueError,TypeError):splitter.setSizes([250,850,235])
        else:splitter.setSizes([250,850,235])
        self._comparison_sizes=[250,850,235]
        if self.settings.value('comparison_hidden',False,type=bool):
            self.comparison_panel.hide();self.comparison_toggle.setText('👁 Show comparison')
        self.elapsed_ms=0
        self.playback_clock=PlaybackClock()
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(25)
        self.recovery_timer=QTimer(self);self.recovery_timer.timeout.connect(self.autosave_recovery);self.recovery_timer.start(60000)
        self.change_anim(self.anim.currentText());self.toggle_mode(initial=True);self.add_workspace_tab("project",f"0::{self._project_name}");self.add_workspace_tab("animation",self.anim.currentText());self.add_workspace_tab("phase","Timeline");self.add_workspace_tab("phase","Rigging");self.select_workspace_key(("animation",self.anim.currentText()))
        QTimer.singleShot(0,self.offer_recovery)
    @staticmethod
    def scroll_panel(content):
        """Keep controls accessible when a window is restored to a small display."""
        panel=QScrollArea()
        panel.setWidgetResizable(True)
        panel.setWidget(content)
        panel.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        panel.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        panel.setMinimumSize(0,0)
        return panel

    def ensure_window_visible(self):
        """Recover an off-screen saved window after monitor/resolution changes."""
        from studio.window_geometry import fit_window_rect
        from PySide6.QtCore import QRect
        screens=QApplication.screens()
        if not screens:return
        available=[screen.availableGeometry() for screen in screens]
        r=self.frameGeometry()
        x,y,w,h=fit_window_rect((r.x(),r.y(),r.width(),r.height()),
            [(g.x(),g.y(),g.width(),g.height()) for g in available])
        if self.isMaximized():return
        if (x,y,w,h)!=(r.x(),r.y(),r.width(),r.height()):
            self.setGeometry(QRect(x,y,w,h))

    def check_for_updates(self):
        if not UPDATE_MANIFEST_URL or not UPDATE_PUBLIC_KEY_B64:
            QMessageBox.information(self, 'Updates not configured',
                'Secure updates will be enabled after the official release signing key and update feed are configured.\n'
                'You can still install official releases manually.')
            return
        if getattr(self, '_update_worker', None) and self._update_worker.isRunning():
            return
        self.status.setText('Checking for a signed update…')
        self._update_worker = UpdateCheckWorker(self)
        self._update_worker.result.connect(self.update_check_result)
        self._update_worker.start()

    def update_check_result(self, payload, error):
        if error:
            QMessageBox.warning(self, 'Update check failed', error)
        elif not payload:
            QMessageBox.information(self, 'Updates', 'You are running the latest available version.')
        else:
            answer = QMessageBox.question(self, 'Update available',
                f"Version {payload['version']} is available. Download its verified installer?\n"
                'Your open creature projects will not be closed or changed.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if answer == QMessageBox.StandardButton.Yes:
                folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / 'updates'
                filename = f"SlimeHouseFriendlyAnimator-Setup-{payload['version']}.exe"
                self._update_download_worker = UpdateDownloadWorker(payload, folder / filename, self)
                self._update_download_worker.result.connect(self.update_download_result)
                self.status.setText('Downloading and verifying signed update…')
                self._update_download_worker.start()
                return
        self.status.setText('Update check finished.')

    def update_download_result(self, installer, error):
        if error:
            QMessageBox.warning(self, 'Update download failed', error)
            self.status.setText('Update download failed; current installation unchanged.')
            return
        answer = QMessageBox.question(self, 'Verified installer ready',
            'The update installer was downloaded and verified.\n'
            'Save any changes and close Friendly Animator to run the installer now?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            self.status.setText(f'Verified installer saved: {installer}')
            return
        if not self.confirm_unsaved_projects(list(self._projects)):
            self.status.setText('Update postponed; your projects remain open.')
            return
        # Windows cannot replace a running application. Launch the installer
        # independently and close the GUI; the installer handles file replacement.
        import subprocess
        try:
            if sys.platform != 'win32':
                raise RuntimeError('Installer handoff is supported on Windows only')
            subprocess.Popen([str(installer)], close_fds=True)
        except Exception as exc:
            QMessageBox.warning(self, 'Could not start installer', str(exc))
            return
        self.close()

    def show_technical_checks(self):
        """User-invoked technical checks; no automatic pop-ups or artistic judgments."""
        issues=check_animation(self.model,self.anim.currentText())
        if not issues:
            QMessageBox.information(self,'Animation check','No technical problems found in the saved poses.\nYour artistic choices are always yours!')
            return
        details='\n\n'.join(f'• {issue.message}\n  Try: {issue.action}' for issue in issues)
        QMessageBox.information(self,'Animation check',details)

    def refresh_buddy(self,*_):
        enabled=self.buddy_toggle.isChecked()
        self.buddy_station.setVisible(enabled)
        self.buddy_details.setVisible(enabled)
        self.pose_tip.setVisible(enabled)
        self.slimer_buddy_tip.setVisible(enabled and self.slimer_toggle.isChecked())
        if hasattr(self,'buddy_mascot'):self.buddy_mascot.setVisible(enabled)
        if hasattr(self,'buddy_bubble'):self.buddy_bubble.setVisible(enabled)
        if enabled:
            self.buddy_details.setText(station_guide(self.buddy_station.currentText()))

    def toggle_comparison(self):
        if self.comparison_panel.isVisible():
            self._comparison_sizes=self.main_splitter.sizes()
            self.comparison_panel.hide()
            self.comparison_toggle.setText('👁 Show comparison')
            self.status.setText('Comparison hidden — enjoy the extra canvas room!')
        else:
            self.comparison_panel.show()
            sizes=self._comparison_sizes
            if len(sizes)==3 and sizes[2]>0:self.main_splitter.setSizes(sizes)
            self.comparison_toggle.setText('👁 Hide comparison')
            self.status.setText('Comparison restored. Drag the divider to adjust its width.')

    def workspace_tab_context_menu(self,pos):
        index=self.workspace_tabs.tabAt(pos)
        if index<0:return
        menu=QMenu(self)
        close=menu.addAction('✕ Close this tab')
        close.setEnabled(len(self._workspace_tab_keys)>1)
        action=menu.exec(self.workspace_tabs.mapToGlobal(pos))
        if action==close:self.close_workspace_tab(index)

    def close_workspace_tab(self,index):
        if not (0<=index<len(self._workspace_tab_keys)) or len(self._workspace_tab_keys)<=1:return
        key=self._workspace_tab_keys[index]
        if key[0]=='project':
            project_id=int(key[1].split('::',1)[0])
            self.close_creature_project(project_id)
            return
        if self._active_workspace==key and key[0]=='animation':
            self._workspace_frames[key]=self.frame
        self._switching_tab=True
        try:
            self._workspace_tab_keys.pop(index)
            self.workspace_tabs.removeTab(index)
        finally:self._switching_tab=False
        current=self.workspace_tabs.currentIndex()
        self._active_workspace=None
        if current>=0:self.switch_workspace_tab(current)
        self.status.setText('Tab closed. Your creature and animation data are safe.')

    def autosave_recovery(self):
        self.preserve_pose_draft()
        # Every open creature has its own snapshot; switching tabs cannot overwrite it.
        self._projects[self._active_project_id]=self.model
        failures=[]
        for project_id, model in list(self._projects.items()):
            if not model.parts or not self.project_is_dirty(project_id):continue
            try:write_project_recovery(model,project_id)
            except Exception as exc:failures.append(str(exc))
        if failures:self.status.setText('Autosave incomplete: '+failures[0])

    def offer_recovery(self):
        paths=list_project_recoveries()
        legacy=recovery_path()
        if legacy.exists():paths.insert(0,legacy)
        if not paths:return
        answer=QMessageBox.question(self,'Recover creatures?',
            f'Found {len(paths)} creature recovery snapshot(s). Restore them as separate tabs?\n'
            'Choose No to discard the recovery copies.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer==QMessageBox.StandardButton.No:
            for path in paths:discard_recovery(path)
            return
        restored=0
        for path in paths:
            try:
                model=read_recovery(path)
                self.add_project(model,f'Recovered Creature {restored+1}')
                restored+=1
            except Exception as exc:
                QMessageBox.warning(self,'Recovery unavailable',f'{path.name}: {exc}')
        if restored:self.status.setText(f'Restored {restored} creature(s). Save each project to keep it permanently.')

    def closeEvent(self,event):
        self.preserve_pose_draft()
        if not self.confirm_unsaved_projects(list(self._projects)):
            event.ignore()
            return
        sizes=self.main_splitter.sizes() if self.comparison_panel.isVisible() else self._comparison_sizes
        self.settings.setValue('splitter_sizes',sizes)
        self.settings.setValue('comparison_hidden',not self.comparison_panel.isVisible())
        for project_id in list(self._projects):discard_project_recovery(project_id)
        self.settings.setValue("window_geometry",self.saveGeometry())
        super().closeEvent(event)

    def workspace_tab_moved(self,from_index,to_index):
        key=self._workspace_tab_keys.pop(from_index)
        self._workspace_tab_keys.insert(to_index,key)

    def add_workspace_tab(self,kind,name):
        if kind=="animation" and "::" not in name:
            name=animation_key(self._active_project_id,name)[1]
        key=(kind,name)
        if key in self._workspace_tab_keys:return self._workspace_tab_keys.index(key)
        self._workspace_tab_keys.append(key)
        label={"project":"🐾 ","animation":"🎞 ","phase":"⚙ "}.get(kind,"")+(name.split("::",1)[1] if kind in ("project","animation") and "::" in name else name)
        self.workspace_tabs.blockSignals(True)
        index=self.workspace_tabs.addTab(label)
        self.workspace_tabs.blockSignals(False)
        return index

    def select_workspace_key(self,key):
        index=self.add_workspace_tab(*key)
        self.workspace_tabs.setCurrentIndex(index)
        self.switch_workspace_tab(index)

    def switch_workspace_tab(self,index):
        if self._switching_tab or not (0<=index<len(self._workspace_tab_keys)):return
        self._switching_tab=True
        try:
            previous=self._active_workspace
            if previous and previous[0]=="animation":
                self._workspace_frames[previous]=self.frame
            kind,name=self._workspace_tab_keys[index]
            self._active_workspace=(kind,name)
            if kind=="project":
                project_id=int(name.split('::',1)[0]) if '::' in name else 0
                self.activate_project(project_id)
                self.status.setText(f'Creature project: {self._project_name}')
            elif kind=="animation":
                if "::" in name:
                    project_prefix, animation_name=name.split("::",1)
                    target_project=int(project_prefix)
                    if target_project not in self._projects:return
                    if target_project!=self._active_project_id:self.activate_project(target_project)
                else:
                    animation_name=name
                if self.anim.currentText()!=animation_name:self.anim.setCurrentText(animation_name)
                desired=self._workspace_frames.get((kind,name),0)
                count=len(self.model.animations.get(animation_name,[]))
                self.frame=min(desired,max(0,count-1)) if count else 0
                self.refresh_timeline()
                if count:self.load_frame(self.frame)
                else:self.select_step(min(self.frame,max(0,self.steps.count()-1)))
                self.status.setText(f'Editing {animation_name} • pose {self.frame+1}. Changes stay with this pose when you switch.')
            elif kind=="phase":
                tips={"Rigging":"Select a body part on the canvas. Use the yellow joint dot to connect or turn it.",
                      "Timeline":"Choose a pose thumbnail below, then copy, rearrange, or change its duration.",
                      "Export":"Use Export PNG + JSON when your animation is ready.",
                      "Assembly":"Import PNG parts on the left, then drag and resize them on the canvas."}
                self.status.setText(f'{name}: {tips.get(name,"Your work stays available in the animation tabs.")}')
            else:
                self.status.setText(f'{self._project_name} • choose an animation tab or use + to add one.')
        finally:self._switching_tab=False

    def workspace_menu(self):
        menu=QMenu(self)
        menu.addAction('🐾 New creature project',self.new_project)
        menu.addAction('📂 Open another creature',self.open_project)
        menu.addAction('✏ Rename current creature',self.rename_project)
        menu.addSeparator()
        for name in TEMPLATES:
            action=menu.addAction('🎞 '+name)
            action.triggered.connect(lambda checked=False,n=name:self.select_workspace_key(('animation',n)))
        menu.addSeparator()
        for name in ('Assembly','Rigging','Timeline','Export'):
            action=menu.addAction('⚙ '+name)
            action.triggered.connect(lambda checked=False,n=name:self.select_workspace_key(('phase',n)))
        menu.exec(self.add_workspace.mapToGlobal(self.add_workspace.rect().bottomLeft()))

    def turn_part(self, angle):
        if not 0 <= self.selected < len(self.model.parts):return
        if self.model.angles.get(self.selected, 0) == angle % 360:return
        self.remember()
        self.model.rotate_part(self.selected, angle)
        if hasattr(self,'angle'):
            self.angle.blockSignals(True);self.angle.setValue(round(angle)%360);self.angle.blockSignals(False)
        self.refresh()

    def toggle_anchor_mode(self, enabled):
        self.canvas.anchor_mode=enabled
        self.anchor_button.setText('✓ Click your part to place the joint • Done' if enabled else '📍 Place a joint dot')
        self.status.setText('Click your selected part where it connects or bends.' if enabled else 'Joint placement finished.')

    def place_anchor(self,x,y):
        if self.selected<0:return
        self.remember()
        self.model.set_anchor(self.selected,x,y)
        self.anchor_button.setChecked(False)
        self.status.setText('Joint dot placed! Connected parts now follow parent turns.')
        self.refresh()

    def toggle_mode(self,initial=False):
        if not initial:self.advanced=not self.advanced
        self.mode.setText('Advanced Mode ⚙  •  Switch to Easy' if self.advanced else 'Easy Mode 🌱  •  Switch to Advanced')
        self.advanced_label.setVisible(self.advanced)
        self.x.setEnabled(self.advanced);self.y.setEnabled(self.advanced)
    def drag_part(self,dx,dy):
        if not 0<=self.selected<len(self.model.parts):return
        p=self.model.parts[self.selected]
        self.remember()
        self.model.move_with_children(self.selected,dx,dy)
        self.select_asset(self.selected);self.refresh()
    def resize_drag(self,dx,dy):
        if not 0<=self.selected<len(self.model.parts):return
        p=self.model.parts[self.selected];self.remember()
        width=max(1,p['image'].width+dx);height=max(1,p['image'].height+dy)
        if self.lock.isChecked():
            ow,oh=self.model.originals[self.selected].size
            height=max(1,round(width*oh/ow))
        self.model.resize_part(self.selected,width,height)
        self.select_asset(self.selected);self.refresh()
    @staticmethod
    def _slimer_cursor():
        """Small pixel-art slime pointer with a precise top-left hotspot."""
        from PySide6.QtCore import QPoint
        art=QPixmap(24,24);art.fill(Qt.GlobalColor.transparent)
        painter=QPainter(art)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#183d31'));painter.drawRect(2,2,12,12)
        painter.setBrush(QColor('#8ee66c'));painter.drawRect(4,4,8,8)
        painter.setBrush(QColor('#e8fff0'));painter.drawRect(5,6,2,2);painter.drawRect(9,6,2,2)
        painter.setBrush(QColor('#183d31'));painter.drawRect(6,10,4,1)
        painter.setPen(QPen(QColor('#f5fff0'),1));painter.drawLine(0,0,0,3);painter.drawLine(0,0,3,0)
        painter.end()
        return QCursor(art,0,0)

    def slimer_switch_phase(self, name):
        if self.slimer_selection is None:
            return
        previous=getattr(self,'_slimer_current_phase',None)
        if previous:
            self.slimer_phase_masks[previous]=self.slimer_selection.mask.copy()
            self.slimer_phase_transforms[previous]=(self.slimer_dx.value(), self.slimer_dy.value(), self.slimer_turn.value(), self.slimer_scale.value())
            self.slimer_phase_histories[previous]=(self.slimer_selection_undo, self.slimer_selection_redo)
        self._slimer_current_phase=name
        # Transform handles belong to the previous color tab. Keep tab masks
        # and numeric values, but do not carry an active drag into another tab.
        if hasattr(self, 'canvas'):
            self.canvas.slimer_transform_mode=False
            self.canvas.slimer_bounds=None
            self.canvas._slimer_handle=None
            self.canvas._slimer_painting=False
            self.canvas._slimer_last=None
        self._slimer_mouse_transforming=False
        if hasattr(self, 'slimer_drag_toggle'):
            self.slimer_drag_toggle.blockSignals(True)
            try:
                self.slimer_drag_toggle.setChecked(False)
            finally:
                self.slimer_drag_toggle.blockSignals(False)
            self.slimer_drag_toggle.setText('Drag selected pixels (Shift=resize, Alt=rotate)')
        self.slimer_selection.mask=self.slimer_phase_masks.get(name,Image.new('L',self.model.size,0)).copy()
        values=self.slimer_phase_transforms.get(name,(0,0,0,100))
        for spin,value in zip((self.slimer_dx,self.slimer_dy,self.slimer_turn,self.slimer_scale),values):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)
        self.slimer_selection_undo, self.slimer_selection_redo = self.slimer_phase_histories.get(name, ([], []))
        self._slimer_sync_numeric_values()
        self._update_slimer_color_button()
        self.refresh()

    def _update_slimer_color_button(self):
        color=self.slimer_phase_colors.get(self.slimer_phase_picker.currentText(),'#54e88a')
        self.slimer_color_button.setStyleSheet(f'QPushButton {{ border: 2px solid {color}; }}')
        self.slimer_color_button.setToolTip(f'Current Slimer highlight color: {color}. Selection tint is editor-only.')

    def slimer_choose_color(self):
        name=self.slimer_phase_picker.currentText()
        color=QColorDialog.getColor(QColor(self.slimer_phase_colors[name]),self,'Slimer highlight color')
        if color.isValid():
            self.slimer_phase_colors[name]=color.name()
            self._update_slimer_color_button()
            self.refresh()

    def slimer_add_phase(self):
        name,ok=QInputDialog.getText(self,'New animation phase','Phase name:')
        name=name.strip()
        if not ok or not name or name in self.slimer_phase_colors:return
        self.slimer_phase_colors[name]='#ffd166'
        self.slimer_phase_picker.addItem(name)
        self.slimer_phase_picker.setCurrentText(name)

    def cleaner_toggle_mode(self,enabled):
        self.canvas.cleaner_active=enabled
        if enabled and self.slimer_toggle.isChecked():
            self.slimer_toggle.setChecked(False)
        self.canvas.setCursor(Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor)
        self.status.setText('Slime Cleaner: left-drag to erase pixels; Undo restores a stroke.' if enabled else 'Slime Cleaner off.')
        self.refresh()

    def cleaner_start_stroke(self):
        self.remember()  # One undo snapshot for the complete brush stroke.

    def cleaner_paint(self,x,y):
        from studio.slime_cleaner import erase_visible_pixels
        if erase_visible_pixels(self.model.parts,x,y,self.cleaner_brush.value()):
            # The renderer and pose snapshots use originals, not only part images.
            # Keep both representations synchronized so erased pixels stay erased.
            for index, part in enumerate(self.model.parts):
                if index < len(self.model.originals):
                    self.model.originals[index] = part['image'].copy()
        self.refresh()

    def adjust_active_brush_size(self,delta):
        """Route +/- to the currently active brush without changing the other tool."""
        if self.cleaner_toggle.isChecked():
            brush = self.cleaner_brush
            label = 'Slime Cleaner'
        elif self.slimer_toggle.isChecked():
            brush = self.slimer_brush
            label = 'Slimer highlight'
        else:
            return
        target = max(brush.minimum(), min(brush.maximum(), brush.value() + delta))
        brush.setValue(target)
        self.status.setText(f'{label} brush size: {target} px (+ / -)')

    def adjust_slimer_brush_size(self,delta):
        """Change highlight size from the keyboard only when Slimer is active."""
        if not self.slimer_toggle.isChecked():
            return
        current=self.slimer_brush.value()
        target=max(self.slimer_brush.minimum(),min(self.slimer_brush.maximum(),current+delta))
        self.slimer_brush.setValue(target)
        self.status.setText(f'Slimer highlight brush size: {target} px (+ / -)')

    def slimer_toggle_mode(self,enabled):
        if enabled and self.cleaner_toggle.isChecked():
            self.cleaner_toggle.setChecked(False)
        self.canvas.slimer_active=enabled
        self.canvas.setCursor(self._slimer_cursor() if enabled else Qt.CursorShape.ArrowCursor)
        self.canvas.anchor_mode=False if enabled else self.canvas.anchor_mode
        self.slimer_drag_toggle.setEnabled(enabled)
        self.slimer_drag_toggle.setChecked(False)
        self.slimer_selection_undo.clear();self.slimer_selection_redo.clear()
        self._slimer_mouse_transforming=False
        self._slimer_sync_numeric_values()
        if enabled:
            self.slimer_selection=SlimerSelection.empty(self.model.render())
            self.slimer_phase_masks={}
            self.slimer_phase_transforms={}
            self.slimer_phase_histories={}
            self._slimer_current_phase=self.slimer_phase_picker.currentText()
        else:
            self.slimer_selection=None
        self.refresh_buddy()
        self.status.setText('Slimer: left-drag to highlight, right-drag to erase highlights. Click Finish Selecting when ready to move pixels.' if enabled else 'Slimer brush disabled.')
        self.refresh()

    def slimer_finish_selecting(self):
        """Turn highlighted pixels into a movable, uncommitted Slimer selection.

        The floating selection is deliberately not an Asset Library layer until
        Place as Layer is pressed; this keeps cancel/edit safe and undoable.
        """
        if not self.slimer_toggle.isChecked():
            self.status.setText('Activate Slimer, then highlight the pixels you want to move.')
            return
        if self.slimer_selection is None or self.slimer_selection.mask.getbbox() is None:
            self.status.setText('No pixels highlighted. Paint a selection before Finish Selecting.')
            return
        self.slimer_drag_toggle.setChecked(True)
        self.refresh()
        self.status.setText('Selection ready: drag to move, Shift-drag to resize, Alt-drag to rotate. Use Edit Selection to change highlights, or place the result.')

    def slimer_drag_mode(self,enabled):
        self.canvas.slimer_transform_mode=enabled
        self.canvas.update()
        self.slimer_drag_toggle.setText('Edit Selection (return to highlighting)' if enabled else 'Drag selected pixels (Shift=resize, Alt=rotate)')
        self.refresh()
        self.status.setText('Drag to move; hold Shift while dragging to resize, or Alt to rotate.' if enabled else 'Paint with left mouse; erase highlight with right mouse.')

    def _slimer_snapshot(self):
        return (self.slimer_selection.mask.copy(), self.slimer_dx.value(),
                self.slimer_dy.value(), self.slimer_scale.value(), self.slimer_turn.value())

    def _slimer_restore(self, snapshot):
        mask, dx, dy, scale, turn = snapshot
        self.slimer_selection.mask = mask.copy()
        for widget, value in ((self.slimer_dx,dx),(self.slimer_dy,dy),
                              (self.slimer_scale,scale),(self.slimer_turn,turn)):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)
        self._slimer_sync_numeric_values()
        self.refresh()

    def slimer_numeric_changed(self, control, value):
        """Record the previous numeric state before a manual spinner adjustment.

        Mouse-driven transforms already record one snapshot at drag start; avoid
        generating duplicate history entries for their intermediate updates.
        """
        if (self.slimer_selection is not None and not self._slimer_numeric_replaying
                and not getattr(self, '_slimer_mouse_transforming', False)):
            snapshot = list(self._slimer_snapshot())
            slot = {self.slimer_dx: 1, self.slimer_dy: 2,
                    self.slimer_scale: 3, self.slimer_turn: 4}[control]
            # QSpinBox.valueChanged runs after its value has changed. Capture
            # the previous value tracked from the last completed adjustment.
            previous = getattr(self, '_slimer_numeric_values', {}).get(control, value)
            if previous != value:
                snapshot[slot] = previous
                self.slimer_selection_undo.append(tuple(snapshot))
                self.slimer_selection_redo.clear()
        if not hasattr(self, '_slimer_numeric_values'):
            self._slimer_numeric_values = {}
        self._slimer_numeric_values[control] = value
        self.refresh()

    def _slimer_sync_numeric_values(self):
        self._slimer_numeric_values = {spin: spin.value() for spin in
            (self.slimer_dx, self.slimer_dy, self.slimer_scale, self.slimer_turn)}

    def slimer_end_transform(self):
        self._slimer_mouse_transforming=False
        self._slimer_sync_numeric_values()

    def slimer_start_stroke(self):
        if self.slimer_selection is None:return
        self.slimer_selection_undo.append(self._slimer_snapshot())
        self.slimer_selection_redo.clear()

    def slimer_start_transform(self):
        if self.slimer_selection is None or self.slimer_selection.mask.getbbox() is None:return
        # One mouse gesture is one history entry, even with many move events.
        self.slimer_selection_undo.append(self._slimer_snapshot())
        self.slimer_selection_redo.clear()
        self._slimer_mouse_transforming=True

    def slimer_undo_selection(self):
        if self.slimer_selection is None or not self.slimer_selection_undo:return
        self.slimer_selection_redo.append(self._slimer_snapshot())
        self._slimer_restore(self.slimer_selection_undo.pop())

    def slimer_redo_selection(self):
        if self.slimer_selection is None or not self.slimer_selection_redo:return
        self.slimer_selection_undo.append(self._slimer_snapshot())
        self._slimer_restore(self.slimer_selection_redo.pop())

    def slimer_drag_transform(self,dx,dy,mode):
        if self.slimer_selection is None or self.slimer_selection.mask.getbbox() is None:return
        if mode=='rotate':self.slimer_turn.setValue(self.slimer_turn.value()+dx+dy)
        elif mode=='scale':self.slimer_scale.setValue(self.slimer_scale.value()+dx+dy)
        else:
            self.slimer_dx.setValue(self.slimer_dx.value()+dx)
            self.slimer_dy.setValue(self.slimer_dy.value()+dy)

    def slimer_paint(self,x,y,erase):
        if self.slimer_selection is None:return
        if 0<=x<self.model.size[0] and 0<=y<self.model.size[1]:
            self.slimer_selection.paint(x,y,(self.slimer_brush.value()-1)//2,erase)
            self.refresh()

    def slimer_preview(self):
        if self.slimer_selection is None:return Image.new('RGBA',self.model.size)
        bounds=self.slimer_selection.mask.getbbox()
        if bounds is None:return Image.new('RGBA',self.model.size)
        scale=self.slimer_scale.value()/100
        return self.slimer_selection.transform(self.slimer_dx.value(),self.slimer_dy.value(),
            max(1,round((bounds[2]-bounds[0])*scale)),max(1,round((bounds[3]-bounds[1])*scale)),self.slimer_turn.value())

    def slimer_confirm_all_placements(self):
        """Place all nonempty color tabs together as one independent layer.

        Preserve each tab's transform and original-pixel mask. A single
        placement uses one history snapshot, rather than committing tabs in
        sequence and accidentally resampling already-edited artwork.
        """
        from PIL import ImageChops
        if self.slimer_selection is None:
            self.status.setText('Activate Slimer and highlight pixels first.')
            return
        active = self.slimer_phase_picker.currentText()
        self.slimer_phase_masks[active] = self.slimer_selection.mask.copy()
        self.slimer_phase_transforms[active] = (self.slimer_dx.value(), self.slimer_dy.value(),
                                                self.slimer_turn.value(), self.slimer_scale.value())
        layers = []
        union = Image.new('L', self.model.size, 0)
        # Use the current unmodified source for every phase, not the result
        # of an earlier phase's placement.
        source = self.model.render().copy()
        for name in self.slimer_phase_colors:
            mask = self.slimer_phase_masks.get(name)
            if mask is None or mask.getbbox() is None:
                continue
            dx, dy, turn, scale = self.slimer_phase_transforms.get(name, (0, 0, 0, 100))
            selection = SlimerSelection(source.copy(), mask.copy())
            bounds = mask.getbbox()
            transformed = selection.transform(dx, dy,
                max(1, round((bounds[2]-bounds[0]) * scale / 100)),
                max(1, round((bounds[3]-bounds[1]) * scale / 100)), turn)
            layers.append(transformed)
            union = ImageChops.lighter(union, mask)
        if not layers:
            self.status.setText('Highlight pixels in at least one color tab first.')
            return
        if self.slimer_move_original.isChecked() and not self._slimer_original_erase_safe(union):
            self.status.setText('Move Original is unavailable for rotated or resized layers. Use Copy Pixels instead.')
            return
        self.remember()
        if self.slimer_move_original.isChecked():
            self._slimer_erase_original_layers(union)
        combined = Image.new('RGBA', self.model.size)
        for layer in layers:
            # Binary masks retain exact pixel RGBA, including partial alpha.
            opaque = layer.getchannel('A').point(lambda a: 255 if a else 0)
            combined.paste(layer, (0, 0), opaque)
        existing = {part.get('name', '') for part in self.model.parts}
        number = 1
        while f'Slimer Layer {number:03d}' in existing:
            number += 1
        self.model.import_part(f'Slimer Layer {number:03d}', combined)
        self.assets.addItem(self.model.parts[-1]['name'])
        self.assets.setCurrentRow(len(self.model.parts)-1)
        self.sync_slimer_asset_labels()
        self.slimer_clear()
        self.status.setText(f'Confirmed {len(layers)} color selections as one layer. Undo reverses the whole placement.')
        self.refresh()

    def slimer_clear(self):
        # Clearing a finished selection must also discard its floating handles.
        # Otherwise a later highlight can inherit stale transform-mode UI.
        self.canvas.slimer_transform_mode = False
        self.canvas.slimer_bounds = None
        self.canvas._slimer_handle = None
        self.canvas._slimer_painting = False
        self.canvas._slimer_last = None
        self.slimer_drag_toggle.blockSignals(True)
        try:
            self.slimer_drag_toggle.setChecked(False)
        finally:
            self.slimer_drag_toggle.blockSignals(False)
        if self.slimer_selection is not None:self.slimer_selection=SlimerSelection.empty(self.model.render())
        self.slimer_phase_masks={}
        self.slimer_phase_transforms={}
        self.slimer_phase_histories={}
        self._slimer_current_phase=self.slimer_phase_picker.currentText()
        self.slimer_selection_undo.clear();self.slimer_selection_redo.clear()
        for spin,value in ((self.slimer_dx,0),(self.slimer_dy,0),(self.slimer_turn,0),(self.slimer_scale,100)):
            spin.blockSignals(True);spin.setValue(value);spin.blockSignals(False)
        self._slimer_sync_numeric_values()
        self.refresh()

    def _slimer_transformed_erase_plan(self, mask):
        """Return a safe single-layer source erase plan, or None.

        Multiple visible layers and pose-specific source buffers remain excluded.
        The selection must cover every rendered occurrence of each source pixel.
        """
        from studio.pixel_source_mapping import (rendered_source_indices,
            plan_complete_source_erase)
        states = self.model.resolved_pose()
        visible = [i for i, state in enumerate(states) if state.get('visible', True)]
        if len(visible) != 1:
            return None
        i = visible[0]
        state = states[i]
        part = self.model.parts[i]
        if i >= len(self.model.originals) or state.get('source_png'):
            return None
        source = self.model.originals[i]
        if source.size != part['image'].size or source.tobytes() != part['image'].tobytes():
            return None
        w = max(1, int(state.get('width', source.width)))
        h = max(1, int(state.get('height', source.height)))
        mapping = rendered_source_indices(source.size, self.model.size,
            int(state['x']), int(state['y']), w, h,
            float(state.get('angle', 0)), self.model.anchors.get(i, [w // 2, h // 2]))
        alpha = self.model.render_part(i, state).getchannel('A')
        plan = plan_complete_source_erase(mapping, alpha, mask)
        if plan is None:
            return None
        # Reject any selected visible pixels that have no mapped source.
        for label, a, selected in zip(mapping.get_flattened_data(),
                                     alpha.get_flattened_data(),
                                     mask.get_flattened_data()):
            if selected and a and label <= 0:
                return None
        return i, plan

    def _slimer_original_erase_safe(self, mask=None):
        """Only erase when canvas pixels map 1:1 to editable source pixels.

        Inspect resolved transforms, not merely local angles: an attached child
        can inherit rotation or movement from a parent without a local angle.
        """
        states = self.model.resolved_pose()
        if mask is not None and getattr(self, '_slimer_transformed_erase_plan', lambda _mask: None)(mask) is not None:
            return True
        for i, state in enumerate(states):
            if not state.get('visible', True):
                continue
            if float(state.get('angle', 0)) % 360:
                return False
            # Pure inherited translation is an exact 1:1 pixel mapping.
            # The erase routine uses resolved canvas coordinates below.
            part = self.model.parts[i]
            if i >= len(self.model.originals):
                return False
            source = self.model.originals[i]
            if state.get('source_png'):
                source = self.model._decode_source(state['source_png'])
            # Erasing edits part['image'] and originals. If this pose renders a
            # different saved source, those buffers do not describe its pixels.
            # Refuse the destructive move until pose-aware source editing exists.
            # The erase routine mutates both the live part and originals.
            # Both must match the exact source used by the renderer; otherwise
            # a pose-local source could conceal edits or erase another pose.
            if (source.size != part['image'].size
                    or source.tobytes() != part['image'].tobytes()
                    or source.size != self.model.originals[i].size
                    or source.tobytes() != self.model.originals[i].tobytes()):
                return False
            if (int(state.get('width', source.width)),
                    int(state.get('height', source.height))) != source.size:
                return False
        return True

    def _slimer_erase_original_layers(self, mask):
        """Clear selected rendered pixels from their topmost contributing layer.

        Clearing every visible layer would destroy hidden/underlying artwork
        when multiple source layers overlap at the same canvas coordinate.
        """
        from PIL import ImageChops
        plan = getattr(self, '_slimer_transformed_erase_plan', lambda _mask: None)(mask)
        if plan is not None:
            from studio.pixel_source_mapping import erase_planned_source_pixels
            i, indices = plan
            image = erase_planned_source_pixels(self.model.originals[i], indices)
            self.model.parts[i]['image'] = image.copy()
            self.model.originals[i] = image.copy()
            return
        remaining = mask.convert('L').point(lambda a: 255 if a else 0)
        states = self.model.resolved_pose()
        for i in range(len(self.model.parts) - 1, -1, -1):
            part = self.model.parts[i]
            if not states[i].get('visible', True) or remaining.getbbox() is None:
                continue
            image = part['image'].convert('RGBA').copy()
            state = states[i]
            x, y = int(state['x']), int(state['y'])
            local = remaining.crop((x, y, x + image.width, y + image.height))
            # Only pixels actually present in this layer can consume the mask.
            present = image.getchannel('A').point(lambda a: 255 if a else 0)
            consumed = ImageChops.darker(local, present)
            if consumed.getbbox() is None:
                continue
            image.putalpha(ImageChops.subtract(image.getchannel('A'), consumed))
            part['image'] = image
            if i < len(self.model.originals):
                self.model.originals[i] = image.copy()
            canvas_consumed = Image.new('L', self.model.size, 0)
            canvas_consumed.paste(consumed, (x, y))
            remaining = ImageChops.subtract(remaining, canvas_consumed)

    def _slimer_commit(self,as_frame):
        selection=self.slimer_selection
        if selection is None or selection.mask.getbbox() is None:
            self.status.setText('Highlight some pixels with the Slimer brush first.');return
        # Validate before touching the timeline. A rejected Move Original must
        # not save a dirty draft or alter the current frame's recovery state.
        if self.slimer_move_original.isChecked() and not self._slimer_original_erase_safe(selection.mask):
            self.status.setText('Move Original is unavailable for this source/selection. Use Copy Pixels instead.')
            return
        # Commit the current pose BEFORE adding a new part. Otherwise an active
        # draft can accidentally save the new Slimer layer into the previous pose.
        if as_frame:
            self.preserve_pose_draft()
        self.remember()  # A complete placement, including new layer/frame, is ONE undo step.
        result=self.slimer_preview()  # Selected pixels only, not the full creature.
        if self.slimer_move_original.isChecked():
            # Clear only the active working pose; the previous timeline pose was
            # snapshotted above before this destructive part of the operation.
            self._slimer_erase_original_layers(selection.mask)
        if as_frame:
            # Reuse the dedicated Slimer overlay layer instead of appending a
            # second/third/etc. "Slimer pose" asset on every Place Frame click.
            # Pose snapshots contain their own source_png, so changing this
            # layer's source for the NEW frame cannot rewrite an older frame.
            overlay_index=next((i for i,p in enumerate(self.model.parts)
                if p.get('name') == 'Slimer pose overlay'), None)
            if overlay_index is None:
                self.model.import_part('Slimer pose overlay', result)
                overlay_index=len(self.model.parts)-1
                self.assets.addItem(self.model.parts[-1]['name'])
            else:
                from PIL import Image
                # An overlay hidden by apply_pose() belongs to another pose.
                # Never resurrect its cached pixels in the current frame.
                if self.model.parts[overlay_index].get('visible', True):
                    old_layer=self.model.originals[overlay_index].convert('RGBA').copy()
                else:
                    old_layer=Image.new('RGBA', self.model.size)
                if old_layer.size != tuple(self.model.size):
                    old_layer=old_layer.resize(self.model.size,Image.Resampling.NEAREST)
                # The selected pixels are placed on the existing transparent
                # overlay; previous selections in this pose remain visible.
                # Pixel-art placements must be idempotent. Alpha-compositing a
                # semi-transparent selected pixel repeatedly increases opacity
                # and can corrupt the exact RGBA value. Replace only pixels
                # actually selected, preserving their original alpha.
                placed=result.convert('RGBA')
                selection_mask=placed.getchannel('A').point(lambda a: 255 if a else 0)
                merged=old_layer.copy()
                merged.paste(placed,(0,0),selection_mask)  # binary mask copies exact RGBA
                self.model.originals[overlay_index]=merged.copy()
                self.model.parts[overlay_index]['image']=merged.copy()
                self.model.parts[overlay_index]['x']=0
                self.model.parts[overlay_index]['y']=0
                self.model.parts[overlay_index]['visible']=True
                self.model.angles[overlay_index]=0
            self.assets.setCurrentRow(overlay_index)
        else:
            # Every explicit Place as Layer creates a separate, uniquely named asset.
            existing={part.get('name', '') for part in self.model.parts}
            number=1
            while f'Slimer Layer {number:03d}' in existing:
                number+=1
            self.model.import_part(f'Slimer Layer {number:03d}',result)
            self.assets.addItem(self.model.parts[-1]['name'])
            self.assets.setCurrentRow(len(self.model.parts)-1)
        if as_frame:
            name=self.anim.currentText()
            # The previous frame is already finalized. The new part exists only
            # in the new frame snapshot, not in the older pose's saved state.
            index=self.model.insert_frame(name,self.frame+1)
            self._pose_draft_dirty=False
            self.select_timeline_pose(index)
        self.sync_slimer_asset_labels()
        self.slimer_clear()
        self.status.setText('Slimer placement complete: originals moved.' if self.slimer_move_original.isChecked() else 'Slimer placement complete: originals copied.')
        self.refresh()

    def slimer_place_layer(self):self._slimer_commit(False)
    def slimer_place_frame(self):
        """Create a new pose even when no pixels have been highlighted.

        A plain Place Frame is a snapshot, not a destructive Slimer move.
        """
        if not self.model.parts:
            QMessageBox.warning(self,'No artwork','Import creature artwork first.')
            return
        if self.slimer_selection is None or self.slimer_selection.mask.getbbox() is None:
            self.preserve_pose_draft()
            self.remember()
            name=self.anim.currentText()
            index=self.model.insert_frame(name,self.frame+1)
            self.select_timeline_pose(index)
            self.status.setText(f'Placed independent pose {index+1} without changing artwork.')
            return
        self._slimer_commit(True)

    def remember(self):
        self.history.record(self.model)
        self.mark_pose_draft()

    def _after_history_change(self):
        self.assets.blockSignals(True)
        self.assets.clear()
        self.assets.addItems([p['name'] for p in self.model.parts])
        self.assets.blockSignals(False)
        self.selected=min(self.selected,len(self.model.parts)-1)
        self.assets.setCurrentRow(self.selected)
        self.refresh_parent_picker()
        self.refresh_timeline()
        self.refresh()

    def _timeline_history_signature(self):
        """Identity/order of saved poses, excluding ordinary pixel edits."""
        return tuple((name, tuple(self.model.pose_id(name, i)
                                  for i in range(len(poses))))
                     for name, poses in sorted(self.model.animations.items()))

    def _history_selection(self):
        """Remember the selected pose by identity, not its shifting row number."""
        animation = self.anim.currentText()
        poses = self.model.animations.get(animation, [])
        pose_id = self.model.pose_id(animation, self.frame) if 0 <= self.frame < len(poses) else None
        return animation, pose_id, self.frame

    def _after_history_restore(self, previous_timeline, selection):
        """Restore history, animation selector, pose canvas and Slimer source together."""
        previous_animation, pose_id, old_index = selection
        animation = self.model.current
        if animation not in self.model.animations:
            animation = (previous_animation if previous_animation in self.model.animations
                         else next(iter(self.model.animations), ''))
        if animation != previous_animation:
            pose_id = None  # IDs from another animation must never select this pose.
            old_index = 0
        # History may replace the entire pixel source. A live Slimer selection
        # refers to pixels from before Undo/Redo and must not survive that swap.
        self._pose_draft_key = None
        self._pose_draft_dirty = False
        self._reset_slimer_for_project_change()
        if self.anim.currentText() != animation:
            self.anim.blockSignals(True)
            try:
                self.anim.setCurrentText(animation)
            finally:
                self.anim.blockSignals(False)
        self._after_history_change()
        poses = self.model.animations.get(animation, [])
        if not poses:
            self.frame = 0
            self._pose_draft_key = None
        else:
            ids = [self.model.pose_id(animation, i) for i in range(len(poses))]
            index = ids.index(pose_id) if pose_id in ids else min(max(old_index, 0), len(poses) - 1)
            self.select_timeline_pose(index)
        if self._timeline_history_signature() != previous_timeline:
            self._timeline_structure_changed()

    def undo(self):
        if self.slimer_toggle.isChecked() and self.slimer_selection_undo:
            self.slimer_undo_selection();self.status.setText("Undid Slimer selection or transform.");return
        previous_timeline = self._timeline_history_signature()
        selection = self._history_selection()
        if self.history.undo(self.model):
            self._pose_draft_dirty=False
            self._after_history_restore(previous_timeline, selection)
            self.status.setText('Undid the last edit. Redo restores it.')

    def redo(self):
        if self.slimer_toggle.isChecked() and self.slimer_selection_redo:
            self.slimer_redo_selection();self.status.setText("Restored Slimer selection or transform.");return
        previous_timeline = self._timeline_history_signature()
        selection = self._history_selection()
        if self.history.redo(self.model):
            self._pose_draft_dirty=False
            self._after_history_restore(previous_timeline, selection)
            self.status.setText('Restored the edit.')

    def move_layer(self,direction):
        i=self.selected
        if i<0 or not 0<=i+direction<len(self.model.parts):return
        self.remember()
        if self.model.reorder_part(i,direction):
            self.assets.clear();self.assets.addItems([p['name'] for p in self.model.parts])
            self.assets.setCurrentRow(i+direction);self.refresh_parent_picker();self.refresh()
    def refresh_parent_picker(self):
        if not hasattr(self,'parent_picker'):return
        current=self.parent_picker.currentData()
        self.parent_picker.blockSignals(True);self.parent_picker.clear()
        for i,part in enumerate(self.model.parts):
            if i != self.selected:self.parent_picker.addItem(part['name'],i)
        pos=self.parent_picker.findData(current)
        if pos>=0:self.parent_picker.setCurrentIndex(pos)
        self.parent_picker.blockSignals(False)

    def connect_part(self):
        parent=self.parent_picker.currentData()
        if self.selected<0 or parent is None:
            self.status.setText('First select a part, then choose what it connects to.');return
        try:
            self.remember();self.model.attach(self.selected,parent)
            self.status.setText(f"Connected {self.model.parts[self.selected]['name']} to {self.model.parts[parent]['name']}! Move the parent to try it.")
        except ValueError as e:QMessageBox.information(self,'Connection tip',str(e))

    def disconnect_part(self):
        if self.selected<0:return
        self.remember();self.model.detach(self.selected)
        self.status.setText('Part unlinked. You can move it independently.')

    def import_assets(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Import creature assets','','PNG (*.png)')
        for path in paths:
            try:
                im=Image.open(path).convert('RGBA')
                cw,ch=self.model.size
                if im.width>cw or im.height>ch:
                    answer=QMessageBox.question(self,'Large PNG asset',f'{Path(path).name} is {im.width} × {im.height} pixels, larger than the {cw} × {ch} canvas.\n\nFit inside canvas without cropping? (No keeps original size.)',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Yes)
                    if answer==QMessageBox.StandardButton.Cancel:continue
                    if answer==QMessageBox.StandardButton.Yes:
                        im.thumbnail((cw,ch),Image.Resampling.NEAREST)
                self.remember();self.model.import_part(Path(path).stem,im)
                self.assets.addItem(Path(path).stem)
            except Exception as e:QMessageBox.warning(self,'Import failed',str(e))
        if paths:self.refresh_parent_picker()
        if paths:self.assets.setCurrentRow(len(self.model.parts)-1)
        self.refresh()
    def select_asset(self,i):
        self.selected=i
        self.canvas.selected=i
        if i<0 or i>=len(self.model.parts):
            self.active_asset_label.setText('Editing: No asset selected')
            return
        p=self.model.parts[i]
        self.active_asset_label.setText(f"Editing: {self.assets.item(i).text() if self.assets.item(i) else p.get('name', 'Asset')}")
        self.refresh_parent_picker()
        for spin,val in ((self.x,p['x']),(self.y,p['y']),(self.w,p['image'].width),(self.h,p['image'].height)):
            spin.blockSignals(True);spin.setValue(val);spin.blockSignals(False)
        self.angle.blockSignals(True);self.angle.setValue(round(self.model.angles.get(i,0)));self.angle.blockSignals(False)
    def update_asset(self):
        if not 0<=self.selected<len(self.model.parts):return
        p=self.model.parts[self.selected]
        if (p['x'],p['y'],p['image'].width,p['image'].height)!=(self.x.value(),self.y.value(),self.w.value(),self.h.value()):self.remember()
        p['x']=self.x.value();p['y']=self.y.value()
        w,h=self.w.value(),self.h.value()
        if self.lock.isChecked():
            ow,oh=self.model.originals[self.selected].size
            sender=self.sender()
            if sender is self.w:h=max(1,round(w*oh/ow));self.h.blockSignals(True);self.h.setValue(h);self.h.blockSignals(False)
            elif sender is self.h:w=max(1,round(h*ow/oh));self.w.blockSignals(True);self.w.setValue(w);self.w.blockSignals(False)
        self.model.resize_part(self.selected,w,h);self.refresh()
    def _selected_or_tip(self):
        if 0 <= self.selected < len(self.model.parts):
            return True
        self.status.setText('🌱 Choose a PNG part in the Asset Library first, then try that tool.')
        return False

    def flip_selected(self, axis):
        if not self._selected_or_tip():return
        self.remember();self.model.flip_part(self.selected,axis)
        self.select_asset(self.selected);self.refresh()
        self.status.setText('Flipped the selected part. Press Ctrl+Z to undo.')

    def center_selected(self, axis):
        if not self._selected_or_tip():return
        self.remember();self.model.center_part(self.selected,axis)
        self.select_asset(self.selected);self.refresh()
        self.status.setText('Centered the selected part. Press Ctrl+Z to undo.')

    def reset_size(self):
        if not self._selected_or_tip():return
        self.remember();self.model.reset_part_size(self.selected)
        self.select_asset(self.selected);self.refresh()
        self.status.setText('Restored the original PNG size. Press Ctrl+Z to undo.')

    def preserve_pose_draft(self):
        """Keep an edited pose before navigating away, without touching other frames."""
        key=self._pose_draft_key
        if not self._pose_draft_dirty or key is None:return
        project_id,animation,index=key
        if project_id==self._active_project_id and 0<=index<len(self.model.animations.get(animation,[])):
            self.model.save_pose_at(animation,index)
        self._pose_draft_dirty=False

    def mark_pose_draft(self):
        if self._loading_pose:return
        key=self._pose_draft_key
        if key and key[0]==self._active_project_id and 0<=key[2]<len(self.model.animations.get(key[1],[])):
            self._pose_draft_dirty=True

    def begin_pose_draft(self,animation,index):
        self.preserve_pose_draft()
        self._pose_draft_key=(self._active_project_id,animation,index)
        self._pose_draft_dirty=False

    def change_anim(self,name):
        # Switching animations starts the new preview at its first pose.
        # Rebase the clock so elapsed time from the old animation cannot
        # advance the new one on the next timer tick.
        self.restart_playback()
        previous_animation=self.model.current
        self.preserve_pose_draft()
        self._pose_draft_key=None
        self.model.current=name
        if hasattr(self,'workspace_tabs') and not self._switching_tab:
            self.select_workspace_key(('animation',name))
        # Rebuilding the step list used to emit currentRowChanged while the
        # destination animation was only half-loaded. That re-entered
        # select_step(), potentially mixing the old canvas with the new pose.
        self.steps.blockSignals(True)
        try:
            self.steps.clear()
            for i,step in enumerate(TEMPLATES[name]):
                self.steps.addItem(f'{i+1}. {step}')
            self.steps.setCurrentRow(0)
        finally:
            self.steps.blockSignals(False)
        poses=self.model.animations.get(name,[])
        if poses:
            self.select_step(0)
        else:
            # No saved destination pose exists. Keep shared creature base art,
            # but never show a Slimer overlay from the previous animation.
            # Existing saved snapshots own their own overlay pixels, so hiding
            # the live layer here does not alter any saved timeline pose.
            self._pose_draft_key=None
            self.frame=0
            if previous_animation != name:
                for part in self.model.parts:
                    if part.get('name') == 'Slimer pose overlay':
                        part['visible'] = False
        if previous_animation != name:
            # The destination has now been applied (if saved), so derive the
            # fresh Slimer source from the destination rather than the old pose.
            self._reset_slimer_for_project_change()
        if not poses:
            self.refresh()
        self.refresh_timeline()
        self.refresh_preview()
    def select_step(self,index):
        if index<0:return
        animation=self.anim.currentText()
        previous_key=self._pose_draft_key
        next_key=(self._active_project_id,animation,index)
        changing_pose=previous_key is not None and previous_key != next_key
        self.begin_pose_draft(animation,index)
        self.frame=index
        self.instruction.setText(f'Frame {index+1}: {TEMPLATES[animation][index % len(TEMPLATES[animation])]}. Drag parts to move, green corner to resize, blue circle to turn. Then save this pose.')
        poses=self.model.animations.get(animation,[])
        if index<len(poses):self.model.apply_pose(poses[index]);self.select_asset(self.selected)
        if changing_pose:
            self._reset_slimer_for_project_change()
        self.refresh()
    def sync_slimer_asset_labels(self):
        """Number the Slimer overlay by its selected timeline pose, not by layer count.

        The canonical model layer name remains unchanged: the UI label is only a
        presentation of the active pose. This avoids using mutable display names
        as layer identifiers and does not rewrite saved pose snapshots.
        """
        if not hasattr(self, 'assets'):
            return
        animation = self.anim.currentText()
        poses = self.model.animations.get(animation, [])
        number = self.frame + 1 if 0 <= self.frame < len(poses) else None
        for index, part in enumerate(self.model.parts):
            if index >= self.assets.count():
                break
            canonical = part.get('name', '')
            if canonical == 'Slimer pose overlay':
                # A pose predating this layer must not claim ownership of it.
                owned = (number is not None and index < len(poses[self.frame])
                         and poses[self.frame][index].get('visible', True))
                label = f'Slimer Pose {number:03d}' if owned else 'Slimer pose overlay (not in this pose)'
            else:
                label = canonical
            self.assets.item(index).setText(label)
        if 0 <= self.selected < self.assets.count():
            self.active_asset_label.setText(f'Editing: {self.assets.item(self.selected).text()}')

    def refresh_timeline(self):
        if not hasattr(self,'timeline'):return
        self.timeline.blockSignals(True);self.timeline.clear()
        for i,_ in enumerate(self.model.animations.get(self.anim.currentText(),[])):
            # A real rendered miniature helps new animators identify each pose at a glance.
            pose=self.model.animations[self.anim.currentText()][i]
            item_text=f'Pose {i+1} · {self.model.frame_duration(self.anim.currentText(),i)}ms'
            from PySide6.QtWidgets import QListWidgetItem
            item=QListWidgetItem(item_text)
            try:
                image=self.model.render(pose)
                item.setIcon(QIcon(pixmap(image,66)))
            except (ValueError, IndexError, KeyError, OSError) as exc:
                item.setToolTip(f'Preview unavailable: {exc}')
            self.timeline.addItem(item)
        self.timeline.blockSignals(False)
        self.sync_slimer_asset_labels()
        if 0 <= self.frame < self.timeline.count():
            self.timeline.setCurrentRow(self.frame)
    def load_frame(self,index):
        self.elapsed_ms=0
        animation=self.anim.currentText()
        poses=self.model.animations.get(animation,[])
        if 0<=index<len(poses):
            # An unfinished selection is derived from one pose's pixels. It
            # must never be replayed on another pose, even when Slimer remains
            # the active tool. A same-pose refresh should not discard it.
            previous_key=self._pose_draft_key
            next_key=(self._active_project_id,animation,index)
            changing_pose=previous_key is not None and previous_key != next_key
            self.begin_pose_draft(animation,index)
            self.frame=index;self.model.apply_pose(poses[index]);self.select_asset(self.selected)
            if changing_pose:
                self._reset_slimer_for_project_change()
            self.duration.blockSignals(True);self.duration.setValue(self.model.frame_duration(animation,index));self.duration.blockSignals(False)
            self.steps.setCurrentRow(min(index,self.steps.count()-1));self.sync_slimer_asset_labels();self.refresh()
    def save_frame(self):
        """Save only an existing selected pose; never create frames implicitly."""
        if not self.model.parts:
            QMessageBox.warning(self,'No assets','Import creature parts first.')
            return
        name=self.anim.currentText()
        poses=self.model.animations.get(name,[])
        if not 0 <= self.frame < len(poses):
            QMessageBox.information(self,'No selected pose','Use Place Frame to create a pose first.')
            return
        self.remember()
        self.model.save_pose_at(name,self.frame)
        self._pose_draft_key=(self._active_project_id,name,self.frame)
        self._pose_draft_dirty=False
        self.refresh_timeline()
        self.status.setText(f'Saved {name} pose {self.frame+1} without changing other poses.')
        self.refresh()
    def restore_previous_timeline_pose(self):
        """Restore only the selected saved pose, then reload its canvas and thumbnail."""
        name = self.anim.currentText()
        index = self.timeline.currentRow()
        poses = self.model.animations.get(name, [])
        if not 0 <= index < len(poses):
            QMessageBox.information(self, 'No selected pose', 'Select a saved timeline pose first.')
            return
        pose_id = self.model.pose_id(name, index)
        if not self.model.pose_recovery.get(pose_id):
            QMessageBox.information(self, 'No previous version', 'This pose has no earlier saved version to restore.')
            return
        # A restore deliberately discards the current unsaved draft. Do not
        # allow load_frame() to auto-save it over the recovered snapshot.
        self.remember()
        self._pose_draft_dirty = False
        if not self.model.restore_previous_pose(name, index):
            return
        self._pose_draft_key = None
        self.select_timeline_pose(index)
        # The recovered pose is now the only valid selection source. A Slimer
        # selection made against the discarded version must not be replayed.
        # Keep the Slimer tool active, but clear its transient selection state.
        self._reset_slimer_for_project_change()
        self.refresh()
        self.status.setText(f'Restored previous version of {name} pose {index+1}. Save Creature to keep this recovery on disk.')

    def duplicate_frame(self):
        """Append an independent snapshot through the identity-safe model API."""
        self.preserve_pose_draft()
        if not self.model.parts:
            QMessageBox.warning(self, 'No artwork', 'Import creature artwork first.')
            return
        name = self.anim.currentText()
        frames = self.model.animations.get(name, [])
        if not frames:
            QMessageBox.information(self, 'No pose to duplicate', 'Use Place Frame to create your first timeline pose.')
            return
        self.remember()
        # Duplicate the selected saved snapshot, not whatever temporary Slimer
        # overlay happens to be visible on the working canvas.
        source_index = min(max(self.frame, 0), len(frames) - 1)
        index = self.model.copy_frame(name, source_index)
        self._pose_draft_key = None
        self._timeline_structure_changed()
        self.select_timeline_pose(index)
        self.status.setText(f'Duplicated pose {source_index + 1} as pose {index + 1} in {name}.')
    def select_timeline_pose(self,index):
        """Load the requested pose even if the row number did not change.

        A new frame inserted at the same row index as the previously selected
        frame must still load its own snapshot and update the draft identity.
        """
        self.refresh_timeline()
        if not 0 <= index < self.timeline.count():
            return
        self.timeline.blockSignals(True)
        self.timeline.setCurrentRow(index)
        self.timeline.blockSignals(False)
        self.load_frame(index)

    def _timeline_structure_changed(self):
        """Restart preview timing after frame count/order changes.

        Keep the user's Play/Pause choice; never carry elapsed time from a
        different timeline layout into the new one.
        """
        self.restart_playback()

    def insert_pose(self):
        self.preserve_pose_draft()
        if not self.model.parts:
            QMessageBox.warning(self,'Add a creature first','Import your creature parts before adding a pose.');return
        self.remember()
        index=self.model.insert_frame(self.anim.currentText(),self.frame+1)
        self._timeline_structure_changed()
        self.select_timeline_pose(index)
        self.status.setText(f'Added pose {index+1}. Drag parts to make the next movement!')

    def import_pose_png(self):
        """Import a full-canvas PNG as a NEW independent timeline pose."""
        path,_=QFileDialog.getOpenFileName(self,'Import PNG as new pose','','PNG images (*.png)')
        if not path:return
        try:
            with Image.open(path) as opened:
                image=opened.convert('RGBA')
            if image.size!=tuple(self.model.size):
                QMessageBox.warning(self,'Pose size mismatch',
                    f'The PNG is {image.width} × {image.height} pixels, but this canvas is '
                    f'{self.model.size[0]} × {self.model.size[1]}. Export a frame PNG '
                    'to get the correct transparent canvas dimensions.')
                return
            self.preserve_pose_draft()
            self.remember()
            animation=self.anim.currentText()
            frames=self.model.animations.get(animation,[])
            index=self.model.insert_frame(animation,min(self.frame+1,len(frames)))
            self.model.replace_frame_image(animation,index,image)
            self.assets.addItem(self.model.parts[-1]['name'])
            self._timeline_structure_changed()
            self.select_timeline_pose(index)
            self.status.setText(f'Imported {Path(path).name} as new independent pose {index+1}.')
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'Could not import pose',str(exc))

    def copy_pose(self):
        self.preserve_pose_draft()
        frames=self.model.animations.get(self.anim.currentText(),[])
        if not frames:
            self.insert_pose();return
        self.remember()
        index=self.model.copy_frame(self.anim.currentText(),min(self.frame,len(frames)-1))
        self._timeline_structure_changed()
        self.select_timeline_pose(index)
        self.status.setText('Copied your pose. Make a small change to animate it!')

    def remove_pose(self):
        self.preserve_pose_draft()
        self._pose_draft_key=None
        frames=self.model.animations.get(self.anim.currentText(),[])
        if not frames:return
        self.remember()
        self.model.delete_frame(self.anim.currentText(),min(self.frame,len(frames)-1))
        self._timeline_structure_changed()
        if frames:
            # Load the surviving snapshot; never leave the deleted pose active.
            self.select_timeline_pose(min(self.frame, len(frames)-1))
        else:
            # Deleting the final pose must not leave its Slimer overlay visible
            # as if it were still saved in the empty timeline.
            self.frame = 0
            self._pose_draft_key = None
            self._pose_draft_dirty = False
            for part in self.model.parts:
                if part.get('name') == 'Slimer pose overlay':
                    part['visible'] = False
            self._reset_slimer_for_project_change()
            self.refresh_timeline()
            self.refresh()
        self.status.setText('Pose removed. Use Undo if you change your mind.')

    def shift_pose(self,direction):
        self.preserve_pose_draft()
        self._pose_draft_key=None
        frames=self.model.animations.get(self.anim.currentText(),[])
        if not frames:return
        index=min(self.frame,len(frames)-1)
        if not 0 <= index+direction < len(frames):return
        self.remember()
        self._timeline_structure_changed()
        self.select_timeline_pose(self.model.move_frame(self.anim.currentText(),index,direction))
        self.status.setText('Pose order updated.')

    def change_duration(self, value):
        frames=self.model.animations.get(self.anim.currentText(),[])
        if 0 <= self.frame < len(frames):
            name = self.anim.currentText()
            old_durations = [self.model.frame_duration(name, i) for i in range(len(frames))]
            if old_durations[self.frame] != value:
                self.remember()
                # Consume time already spent playing before changing the timeline.
                if self.play.isChecked():
                    self.elapsed_ms += self.playback_clock.delta_ms() * float(self.speed.currentData())
                self.elapsed_ms = retime_elapsed(old_durations, self.frame, self.elapsed_ms, value, self.loop.isChecked())
            self.model.set_frame_duration(name,self.frame,value)
            self.refresh_timeline()
            summary=timeline_summary([self.model.frame_duration(self.anim.currentText(),i) for i in range(len(frames))])
            self.status.setText(f'Pose timing updated • {summary["seconds"]:.2f}s total for {summary["frames"]} poses. Shorter means faster!')

    def prev_frame(self):
        """Navigate saved poses, not the hidden legacy recipe-step list."""
        poses = self.model.animations.get(self.anim.currentText(), [])
        if poses:
            self.select_timeline_pose(max(0, min(self.frame, len(poses)-1)-1))

    def next_frame(self):
        """Navigate saved poses, respecting the current animation's length."""
        poses = self.model.animations.get(self.anim.currentText(), [])
        if poses:
            self.select_timeline_pose(min(len(poses)-1, max(0, self.frame)+1))
    def play_toggled(self, playing):
        name = self.anim.currentText()
        poses = self.model.animations.get(name, [])
        if playing and not poses:
            self.play.blockSignals(True)
            self.play.setChecked(False)
            self.play.blockSignals(False)
            self.playback_clock.pause()
            self.play.setText('▶ Play your animation')
            self.status.setText('Add a pose first, then press Play.')
            self.refresh_preview()
            return
        if playing:
            durations = [self.model.frame_duration(name, i) for i in range(len(poses))]
            self.elapsed_ms = resume_position(self.elapsed_ms, durations, self.loop.isChecked())
            self.playback_clock.resume()
        else:
            self.playback_clock.pause()
        self.play.setText('⏸ Pause animation' if playing else '▶ Play your animation')
        self.refresh_preview()
    def restart_playback(self,*_):
        self.elapsed_ms=0;self.playframe=0
        if self.play.isChecked():
            self.playback_clock.resume()
        else:
            self.playback_clock.pause()
        self.refresh_preview()
    def tick(self):
        if not self.play.isChecked():return
        name=self.anim.currentText();poses=self.model.animations.get(name,[])
        if not poses:return
        durations=[self.model.frame_duration(name,i) for i in range(len(poses))]
        self.elapsed_ms+=self.playback_clock.delta_ms()*float(self.speed.currentData())
        if not self.loop.isChecked() and self.elapsed_ms>=sum(durations):
            self.elapsed_ms=float(sum(durations))
            self.play.setChecked(False)
        self.refresh_preview()
    def canvas_view_changed(self):
        self.zoom_label.setText(f'{round(self.canvas.zoom*100)}%')
        self.canvas.update()
    def change_preview_zoom(self,step):
        self.preview_zoom=150 if step==0 else max(50,min(600,self.preview_zoom+step))
        self.refresh_preview()

    def export_current_frame(self):
        name=self.anim.currentText()
        poses=self.model.animations.get(name,[])
        pose=poses[self.frame] if 0<=self.frame<len(poses) else None
        filename,_=QFileDialog.getSaveFileName(self,'Export current frame as transparent PNG',f'friendly_frame_{self.frame+1}.png','PNG images (*.png)')
        if filename:
            self.model.render(pose).save(filename,'PNG')
            self.status.setText('Exported transparent frame PNG for editing in Slime House Studios.')

    def export_all_frames(self):
        """Save every timeline pose as a transparent PNG with timing JSON."""
        filename,_=QFileDialog.getSaveFileName(
            self,'Export all animation frames', 'friendly_frames',
            'Frame set base name (*)')
        if not filename:
            return
        destination=Path(filename)
        try:
            images, metadata=self.model.export_individual_frames(destination.parent, destination.stem)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self,'Could not export frames',str(exc))
            return
        self.status.setText(f'Exported {len(images)} transparent pose PNGs and {metadata.name}.')

    def choose_shs_location(self):
        """Let the user choose the installed or portable SHS .exe once."""
        previous=str(self.settings.value('shs_executable','') or '')
        start=str(Path(previous).parent) if previous and Path(previous).is_file() else ''
        exe,_=QFileDialog.getOpenFileName(
            self,'Select Slime House Studios application',start,
            'Windows applications (*.exe)')
        if not exe:
            return None
        selected=Path(exe)
        if selected.suffix.lower()!='.exe' or not selected.is_file():
            QMessageBox.warning(self,'Invalid SHS application','Please select an existing Windows .exe file.')
            return None
        self.settings.setValue('shs_executable',str(selected))
        self.status.setText(f'SHS application location saved: {selected}')
        return str(selected)

    def _locate_shs(self):
        """Reuse the saved application path, or request it from the user."""
        stored=str(self.settings.value('shs_executable','') or '')
        if stored and Path(stored).is_file() and Path(stored).suffix.lower()=='.exe':
            return stored
        if stored:
            QMessageBox.information(self,'SHS location changed',
                'The previously selected SHS application was moved or removed. Please select it again.')
        return self.choose_shs_location()

    def edit_frame_in_shs(self):
        """Export one independent frame to a temporary PNG and open it in SHS."""
        animation=self.anim.currentText()
        poses=self.model.animations.get(animation,[])
        if not 0<=self.frame<len(poses):
            QMessageBox.information(self,'Choose a pose','Save or select a pose first.')
            return
        exe=self._locate_shs()
        if not exe:return
        work=Path(tempfile.mkdtemp(prefix='friendly_animator_shs_'))
        png=work/f'frame_{self.frame+1}.png'
        try:
            self.model.render(poses[self.frame]).save(png,'PNG')
            subprocess.Popen([exe,str(png)])
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'Could not open SHS',str(exc));return
        self._shs_edit=(str(png),self._active_project_id,animation,self.frame)
        self.status.setText('Opened frame in SHS. Save the PNG there, then click Reload SHS Edit.')

    def reload_shs_edit(self):
        """Reload only the originally selected pose, after confirming any context change."""
        if not self._shs_edit:
            QMessageBox.information(self,'No SHS edit','Click Edit Frame in SHS first.')
            return
        path,project_id,animation,index=self._shs_edit
        if project_id!=self._active_project_id or animation!=self.anim.currentText() or index!=self.frame:
            QMessageBox.information(self,'Select original pose','Switch back to the original project, animation, and pose before reloading.')
            return
        try:
            with Image.open(path) as source:edited=source.convert('RGBA')
            if edited.size!=tuple(self.model.size):
                QMessageBox.warning(self,'Canvas size mismatch',f'Edited PNG is {edited.size}; expected {self.model.size}. Keep the canvas size unchanged in SHS.')
                return
            self.preserve_pose_draft();self.remember()
            self.model.replace_frame_image(animation,index,edited)
            self.assets.addItem(self.model.parts[-1]['name'])
            self._pose_draft_key=(self._active_project_id,animation,index)
            self._pose_draft_dirty=False
            self.model.apply_pose(self.model.animations[animation][index])
            self.assets.setCurrentRow(len(self.model.parts)-1)
            self.refresh_timeline();self.refresh()
            self.status.setText(f'Reloaded SHS edit into pose {index+1} only. Main Undo can reverse it.')
        except (OSError,ValueError) as exc:QMessageBox.warning(self,'Could not reload SHS edit',str(exc))

    def replace_current_frame_png(self):
        """Replace only the selected saved pose with an edited full-canvas PNG."""
        animation=self.anim.currentText()
        poses=self.model.animations.get(animation,[])
        if not 0<=self.frame<len(poses):
            QMessageBox.information(self,'Choose a frame','Select a saved frame in the Pose Timeline first.')
            return
        path,_=QFileDialog.getOpenFileName(self,'Replace current frame from Slime House Studios','','PNG images (*.png)')
        if not path:return
        try:
            with Image.open(path) as opened:
                edited=opened.convert('RGBA')
            if edited.size!=tuple(self.model.size):
                QMessageBox.warning(self,'Frame size mismatch',
                    f'This PNG is {edited.width} × {edited.height} pixels. The creature canvas is {self.model.size[0]} × {self.model.size[1]}.\n\nExport the frame first and keep its original canvas dimensions when editing in Slime House Studios.')
                return
            # Capture the current frame before adding a new independent overlay.
            # Existing saved poses keep their own source pixels and remain untouched.
            self.preserve_pose_draft()
            self.remember()
            self.model.replace_frame_image(animation,self.frame,edited)
            self.assets.addItem(self.model.parts[-1]['name'])
            self._pose_draft_key=(self._active_project_id,animation,self.frame)
            self._pose_draft_dirty=False
            self.model.apply_pose(self.model.animations[animation][self.frame])
            self.assets.setCurrentRow(len(self.model.parts)-1)
            self.refresh_timeline()
            self.refresh()
            self.status.setText(f'Replaced only frame {self.frame+1} from PNG. Main Undo reverses this change.')
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'Could not replace frame',str(exc))

    def load_uploaded_reference(self):
        filename,_=QFileDialog.getOpenFileName(self,'Choose an animation reference','','Images (*.png *.gif *.apng)')
        if not filename:return
        from studio.user_reference import read_reference
        try:
            columns=rows=None
            if Path(filename).suffix.lower()=='.png':
                answer=QMessageBox.question(self,'Sprite sheet?','Is this PNG a sprite sheet with multiple frames?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
                if answer==QMessageBox.StandardButton.Yes:
                    columns,ok=QInputDialog.getInt(self,'Sprite sheet','Number of columns:',4,1,100)
                    if not ok:return
                    rows,ok=QInputDialog.getInt(self,'Sprite sheet','Number of rows:',1,1,100)
                    if not ok:return
            frames=read_reference(filename,columns,rows)
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'Cannot open reference',str(exc));return
        self.reference_timer.stop();self.reference_play.setChecked(False)
        self.reference_files=frames;self.reference_index=0
        self.uploaded_reference_toggle.setChecked(True)
        self.render_uploaded_reference()

    def clear_uploaded_reference(self):
        self.reference_timer.stop();self.reference_play.setChecked(False)
        self.reference_files=[];self.reference_index=0
        self.uploaded_reference_image.clear()
        self.uploaded_reference_image.setText('Load an image to use as a visual reference. Not exported.')
        self.reference_status.setText('No reference loaded')

    def render_uploaded_reference(self):
        if not self.reference_files:return
        frame,duration=self.reference_files[self.reference_index]
        zoom=self.reference_zoom.value()
        rgba=frame.convert('RGBA')
        data=rgba.tobytes('raw','RGBA')
        qimage=QImage(data,rgba.width,rgba.height,rgba.width*4,QImage.Format.Format_RGBA8888).copy()
        scaled=QPixmap.fromImage(qimage).scaled(rgba.width*zoom,rgba.height*zoom,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.FastTransformation)
        self.uploaded_reference_image.setPixmap(scaled)
        self.reference_status.setText(f'Frame {self.reference_index+1}/{len(self.reference_files)} · {duration} ms · reference only')
        if self.reference_timer.isActive():self.reference_timer.start(max(20,duration))

    def step_uploaded_reference(self,delta):
        if not self.reference_files:return
        self.reference_index=(self.reference_index+delta)%len(self.reference_files)
        self.render_uploaded_reference()

    def advance_uploaded_reference(self):
        self.step_uploaded_reference(1)

    def toggle_uploaded_reference_play(self,playing):
        self.reference_play.setText('Ⅱ Pause' if playing else '▶ Play')
        if playing and self.reference_files:
            self.reference_timer.start(max(20,self.reference_files[self.reference_index][1]))
        else:self.reference_timer.stop()

    def refresh_preview(self):
        name=self.anim.currentText()
        poses=self.model.animations.get(name,[])
        if poses and (self.play.isChecked() or self.elapsed_ms > 0):
            durations=[self.model.frame_duration(name,i) for i in range(len(poses))]
            creature_index,_=comparison_position(durations,self.elapsed_ms,1,self.loop.isChecked())
        else:
            creature_index=self.frame if 0<=self.frame<len(poses) else None
        pose=poses[creature_index] if creature_index is not None else None
        self.preview.setPixmap(pixmap(self.model.render(pose),self.preview_zoom))
        self.preview.resize(max(150,self.preview_zoom),max(150,self.preview_zoom))
    def refresh(self):
        self.canvas._image_size=self.model.size;self.canvas.parts=self.model.parts;self.canvas.selected=self.selected;self.canvas.anchors=self.model.anchors;self.canvas.angles=self.model.angles
        composed=self.model.render()
        if self.onion.isChecked():
            poses=self.model.animations.get(self.anim.currentText(),[])
            previous=self.model.render(poses[self.frame-1]) if 0<self.frame<=len(poses) else None
            following=self.model.render(poses[self.frame+1]) if self.onion_next.isChecked() and self.frame+1<len(poses) else None
            composed=onion_composite(composed,previous,following)
        if 0<=self.selected<len(self.model.parts):
            from PIL import ImageDraw
            part=self.model.parts[self.selected]
            overlay=Image.new('RGBA',composed.size)
            draw=ImageDraw.Draw(overlay)
            x,y=part['x'],part['y'];w,h=part['image'].size
            draw.rectangle((x,y,x+w,y+h),outline=(163,230,53,255),width=1)
            draw.rectangle((x+w-2,y+h-2,x+w+2,y+h+2),fill=(163,230,53,255))
            ax,ay=self.model.anchors.get(self.selected,[w//2,h//2])
            px,py=x+ax,y+ay
            theta=math.radians(self.model.angles.get(self.selected,0))
            radius=max(14,round(max(w,h)*0.65))
            hx=round(px+radius*math.cos(theta-math.pi/2));hy=round(py+radius*math.sin(theta-math.pi/2))
            draw.line((px,py,hx,hy),fill=(91,185,245,255),width=1)
            draw.ellipse((hx-3,hy-3,hx+3,hy+3),fill=(91,185,245,255),outline=(15,39,51,255))
            composed.alpha_composite(overlay)
        # Joint dots are editor-only guides and never appear in exported sprites.
        if self.model.anchors:
            from PIL import ImageDraw
            guide=Image.new('RGBA',composed.size)
            draw=ImageDraw.Draw(guide)
            for index in self.model.anchors:
                if index>=len(self.model.parts):continue
                ax,ay=self.model.anchor_position(index)
                draw.ellipse((ax-2,ay-2,ax+2,ay+2),fill=(255,204,51,255),outline=(35,40,35,255))
            composed.alpha_composite(guide)
        rgba=composed.convert('RGBA');data=rgba.tobytes('raw','RGBA')
        image=QImage(data,rgba.width,rgba.height,rgba.width*4,QImage.Format.Format_RGBA8888).copy()
        self.canvas.slimer_bounds=None
        confirmed_slimer_preview=None
        if self.slimer_toggle.isChecked() and self.slimer_selection is not None:
            from PIL import ImageDraw
            # Do not even generate a floating preview during highlight painting.
            # Its source pixels and transformed bounds are needed only after
            # Finish Selecting; before then the raw mask is the sole selection.
            if self.canvas.slimer_transform_mode:
                preview=self.slimer_preview()
                confirmed_slimer_preview=preview
                self.canvas.slimer_bounds=preview.getchannel('A').getbbox()
                if self.canvas.slimer_bounds is None and self.slimer_selection.mask.getbbox():
                    x0,y0,x1,y1=self.slimer_selection.mask.getbbox()
                    self.canvas.slimer_bounds=(x0+self.slimer_dx.value(),y0+self.slimer_dy.value(),x1+self.slimer_dx.value(),y1+self.slimer_dy.value())
                composed.alpha_composite(preview)
            else:
                self.canvas.slimer_bounds=self.slimer_selection.mask.getbbox()
            marker=Image.new('RGBA',composed.size)
            # A 10% tint (alpha 26) was nearly invisible on detailed pixel art.
            # Keep the selected color clearly visible without changing source pixels.
            marker.putalpha(self.slimer_selection.mask.point(lambda v: 120 if v else 0))
            chosen=QColor(self.slimer_phase_colors.get(self.slimer_phase_picker.currentText(),'#54e88a'))
            tint=Image.new('RGBA',composed.size,(chosen.red(),chosen.green(),chosen.blue(),0));tint.putalpha(marker.getchannel('A'))
            if not self.canvas.slimer_transform_mode:composed.alpha_composite(tint)
            data=composed.tobytes('raw','RGBA');image=QImage(data,composed.width,composed.height,composed.width*4,QImage.Format.Format_RGBA8888).copy()
        self.canvas.set_art(QPixmap.fromImage(image))
        if hasattr(self, 'slimer_preview_label'):
            if self.slimer_toggle.isChecked() and self.canvas.slimer_transform_mode and self.slimer_selection is not None and self.slimer_selection.mask.getbbox():
                self.slimer_preview_label.setPixmap(pixmap(confirmed_slimer_preview, 132))
                self.slimer_preview_label.setText('')
            else:
                self.slimer_preview_label.clear()
                self.slimer_preview_label.setText('Finish Selecting to show preview' if self.slimer_toggle.isChecked() else 'Activate Slimer to begin')
        self.refresh_preview()
        recipe=TEMPLATES[self.anim.currentText()];step=recipe[self.frame % len(recipe)]
        self.pose_tip.setVisible(self.buddy_toggle.isChecked())
        self.pose_tip.setText("💡 Select a pose in the timeline to edit it. Save Current Pose to keep your changes." if self.buddy_toggle.isChecked() else '')

    def _reset_slimer_for_project_change(self):
        """Discard transient selection state, never project artwork or saved poses.

        The Slimer tool may stay selected across creature tabs. Its source image,
        masks, drag state and transform controls must not survive that boundary.
        """
        self.slimer_selection_undo.clear()
        self.slimer_selection_redo.clear()
        self.slimer_phase_masks={}
        self.slimer_phase_transforms={}
        self.slimer_phase_histories={}
        self._slimer_current_phase=self.slimer_phase_picker.currentText()
        self._slimer_mouse_transforming=False
        self.canvas._slimer_painting=False
        self.canvas._slimer_last=None
        self.canvas._slimer_handle=None
        self.canvas.slimer_bounds=None
        self.canvas.slimer_transform_mode=False
        self.slimer_drag_toggle.blockSignals(True)
        self.slimer_drag_toggle.setChecked(False)
        self.slimer_drag_toggle.blockSignals(False)
        self.slimer_drag_toggle.setText('Drag selected pixels (Shift=resize, Alt=rotate)')
        for control,value in ((self.slimer_dx,0),(self.slimer_dy,0),
                              (self.slimer_turn,0),(self.slimer_scale,100)):
            control.blockSignals(True)
            control.setValue(value)
            control.blockSignals(False)
        self.slimer_selection=(SlimerSelection.empty(self.model.render())
                               if self.slimer_toggle.isChecked() else None)
        self._slimer_sync_numeric_values()

    def activate_project(self,project_id):
        if project_id not in self._projects:return
        self.preserve_pose_draft()
        self._pose_draft_key=None
        if project_id==self._active_project_id:return
        self._projects[self._active_project_id]=self.model
        # Remember the selected timeline index independently for each creature.
        # Project tabs must not inherit another creature's active pose number.
        if not hasattr(self, '_project_timeline_index'):
            self._project_timeline_index = {}
        self._project_timeline_index[self._active_project_id] = self.frame
        self._project_frames[self._active_project_id]=dict(self._workspace_frames)
        self._project_selected[self._active_project_id]=self.selected
        self._project_animation[self._active_project_id]=self.anim.currentText()
        self._project_views[self._active_project_id]=(self.canvas.zoom,self.canvas.pan_x,self.canvas.pan_y)
        self._active_project_id=project_id
        self._workspace_frames=dict(self._project_frames.get(project_id,{}))
        self.model=self._projects[project_id]
        self.canvas.zoom,self.canvas.pan_x,self.canvas.pan_y=self._project_views.get(project_id,(1.0,0.0,0.0))
        self.canvas_view_changed()
        self._project_name=self._project_labels.get(project_id,'Creature')
        self.history=self._project_histories.setdefault(project_id,EditHistory());self.selected=self._project_selected.get(project_id,-1);self.frame=0;self.playframe=0
        self.assets.blockSignals(True)
        self.assets.clear();self.assets.addItems([p['name'] for p in self.model.parts])
        self.assets.blockSignals(False)
        self.refresh_parent_picker()
        remembered=self._project_selected.get(project_id,-1)
        self.assets.setCurrentRow(remembered if 0<=remembered<len(self.model.parts) else (0 if self.model.parts else -1))
        self.anim.blockSignals(True)
        self.anim.setCurrentText(self._project_animation.get(project_id,self.model.current) if self._project_animation.get(project_id,self.model.current) in TEMPLATES else next(iter(TEMPLATES)))
        self.anim.blockSignals(False)
        # Build the destination list without firing a selection event against
        # the previous creature's canvas. Apply the destination's saved pixels
        # BEFORE Slimer captures its new selection source.
        self.steps.blockSignals(True)
        try:
            self.steps.clear()
            for i,step in enumerate(TEMPLATES[self.anim.currentText()]):
                self.steps.addItem(f'{i+1}. {step}')
        finally:
            self.steps.blockSignals(False)
        animation = self.anim.currentText()
        poses = self.model.animations.get(animation, [])
        if poses:
            index = min(max(0, self._project_timeline_index.get(project_id, 0)), len(poses)-1)
            self.frame = index
            self.model.apply_pose(poses[index])
            self._pose_draft_key = (project_id, animation, index)
        else:
            self.frame = 0
            self._pose_draft_key = None
            for part in self.model.parts:
                if part.get('name') == 'Slimer pose overlay':
                    part['visible'] = False
        self._pose_draft_dirty = False
        self.steps.blockSignals(True)
        try:
            self.steps.setCurrentRow(min(self.frame, self.steps.count()-1))
        finally:
            self.steps.blockSignals(False)
        self._reset_slimer_for_project_change()
        self.refresh_timeline();self.refresh()

    def add_project(self,model,label,path=None):
        self._projects[self._active_project_id]=self.model
        self._project_id+=1;project_id=self._project_id
        self._projects[project_id]=model
        self._project_histories[project_id]=EditHistory()
        self._project_views[project_id]=(1.0,0.0,0.0)
        self._project_frames[project_id]={};self._project_selected[project_id]=-1;self._project_animation[project_id]=model.current if model.current in TEMPLATES else next(iter(TEMPLATES))
        self._project_labels[project_id]=label
        if path:self._saved_fingerprints[project_id]=model.content_fingerprint()
        if path:self._project_paths[project_id]=str(path)
        key=('project',f'{project_id}::{label}')
        self.select_workspace_key(key)
        return project_id

    def project_is_dirty(self,project_id):
        model=self.model if project_id==self._active_project_id else self._projects[project_id]
        return model.content_fingerprint()!=self._saved_fingerprints.get(project_id)

    def export_animated(self):
        self.preserve_pose_draft()
        filename,_=QFileDialog.getSaveFileName(
            self,'Choose animation export base filename (GIF + APNG)', 'creature.gif', 'GIF animation (*.gif)')
        if not filename:return
        target=Path(filename)
        basename=target.stem if target.suffix.lower()=='.gif' else target.name
        if not basename.strip():return
        folder=str(target.parent)
        try:
            exported=self.model.export_animations(folder,basename=basename)
            self.status.setText(f'Exported {len(exported)} animation files to {folder}')
        except Exception as exc:
            QMessageBox.warning(self,'Animation export failed',str(exc))

    def confirm_unsaved_projects(self,project_ids):
        """Ask Save/Discard/Cancel for each changed creature, aborting on failed save."""
        self.preserve_pose_draft()
        original_id=self._active_project_id
        for pid in project_ids:
            if pid not in self._projects or not self.project_is_dirty(pid):
                continue
            name=self._project_labels.get(pid,'Creature')
            answer=QMessageBox.question(
                self,'Unsaved creature',
                f'\"{name}\" has unsaved changes.\nSave before closing?',
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save)
            if answer==QMessageBox.StandardButton.Cancel:
                return False
            if answer==QMessageBox.StandardButton.Save:
                if not self.save_project_by_id(pid):
                    return False
        return True

    def save_project_by_id(self,project_id):
        """Save one project without silently overwriting a different project."""
        if project_id not in self._projects:return False
        if project_id==self._active_project_id:self.preserve_pose_draft()
        path=self._project_paths.get(project_id)
        if not path:
            suggested=self._project_labels.get(project_id,'creature')+'.rig.json'
            path,_=QFileDialog.getSaveFileName(self,'Save creature',suggested,'Rig project (*.json)')
            if not path:return False
        model=self.model if project_id==self._active_project_id else self._projects[project_id]
        try:
            model.save_project(path)
        except Exception as exc:
            QMessageBox.warning(self,'Save failed',str(exc))
            return False
        self._project_paths[project_id]=str(path)
        self._saved_fingerprints[project_id]=model.content_fingerprint()
        self._dirty_projects.discard(project_id)
        discard_project_recovery(project_id)
        self.status.setText(f'Saved {path}')
        return True

    def close_creature_project(self,project_id):
        """Close a creature with Save/Discard/Cancel protection."""
        if project_id not in self._projects:return False
        if len(self._projects)<=1:
            self.status.setText('Keep at least one creature open. Use New creature to start fresh.')
            return False
        if not self.confirm_unsaved_projects([project_id]):return False
        key=next((k for k in self._workspace_tab_keys if k[0]=='project' and k[1].startswith(f'{project_id}::')),None)
        if project_id==self._active_project_id:
            next_id=next(pid for pid in self._projects if pid!=project_id)
            self.activate_project(next_id)
        if key in self._workspace_tab_keys:
            index=self._workspace_tab_keys.index(key)
            self._switching_tab=True
            try:
                self._workspace_tab_keys.pop(index);self.workspace_tabs.removeTab(index)
            finally:self._switching_tab=False
        for index in reversed(range(len(self._workspace_tab_keys))):
            kind,name=self._workspace_tab_keys[index]
            if kind=="animation" and name.startswith(f'{project_id}::'):
                self._switching_tab=True
                try:
                    self._workspace_tab_keys.pop(index);self.workspace_tabs.removeTab(index)
                finally:self._switching_tab=False
        for mapping in (self._projects,self._project_labels,self._project_paths,self._project_frames,self._project_selected,self._project_animation,self._project_histories,self._project_views):
            mapping.pop(project_id,None)
        self._dirty_projects.discard(project_id);self._saved_fingerprints.pop(project_id,None)
        discard_project_recovery(project_id)
        self.select_workspace_key(('project',next(k[1] for k in self._workspace_tab_keys if k[0]=='project' and k[1].startswith(f'{self._active_project_id}::'))))
        self.status.setText('Creature tab closed.')
        return True

    def rename_project(self):
        pid=self._active_project_id
        old=self._project_labels[pid]
        name,ok=QInputDialog.getText(self,'Rename creature','Creature name:',text=old)
        if not ok or not name.strip():return
        name=name.strip()
        self._project_labels[pid]=name
        self._project_name=name
        for index,key in enumerate(self._workspace_tab_keys):
            if key[0]=='project' and key[1].startswith(f'{pid}::'):
                new_key=('project',f'{pid}::{name}')
                self._workspace_tab_keys[index]=new_key
                self.workspace_tabs.setTabText(index,'🐾 '+name)
                if self._active_workspace==key:self._active_workspace=new_key
        self.status.setText(f'Renamed creature to {name}.')

    def new_project(self):
        self.add_project(PetSuiteModel(),f'Creature {self._project_id+2}')

    def save_project(self):
        self.save_project_by_id(self._active_project_id)

    def open_project(self):
        path,_=QFileDialog.getOpenFileName(self,'Open creature','','Rig project (*.json)')
        if path:
            try:
                resolved=str(Path(path).resolve())
                for pid,existing in self._project_paths.items():
                    if str(Path(existing).resolve())==resolved:
                        self.select_workspace_key(('project',next(k[1] for k in self._workspace_tab_keys if k[0]=='project' and k[1].startswith(f'{pid}::'))))
                        self.status.setText('That creature is already open; switched to its tab.')
                        return
                model=PetSuiteModel.load_project(path)
                self.add_project(model,Path(path).stem,path)
                self.status.setText(f'Opened {path} in a new project tab')
            except Exception as e:QMessageBox.warning(self,'Open failed',str(e))
    def export(self):
        self.preserve_pose_draft()
        filename,_=QFileDialog.getSaveFileName(
            self,'Choose sprite sheet filename','creature_sheet.png','PNG sprite sheet (*.png)')
        if filename:
            target=Path(filename)
            stem=target.stem if target.suffix.lower()=='.png' else target.name
            basename=stem[:-6] if stem.endswith('_sheet') else stem
            if not basename.strip():return
            try:
                result=self.model.export(target.parent,basename=basename);self.status.setText(f'Exported {result} and JSON metadata')
            except Exception as e:QMessageBox.warning(self,'Export failed',str(e))

def main():
    app=QApplication(sys.argv)
    if '--smoke-test' in sys.argv:
        # Exercise the actual packaged GUI without user interaction.
        # The same executable is used for regular startup and this test.
        try:
            window=Suite()
            window.show()
            app.processEvents()
            if not window.isVisible():
                raise RuntimeError('Main window did not become visible')
            # Exercise transitions with event processing, not only method presence.
            for transition in (window.showMinimized, window.showNormal,
                               window.showMaximized, window.showNormal):
                transition()
                app.processEvents()
            if not window.isVisible() or window.isMinimized() or window.isMaximized():
                raise RuntimeError('Main window failed to restore to normal state')
            # Available geometry differs with taskbars and DPI scaling. Qt's
            # logical coordinates, rather than physical pixels, are authoritative.
            screen=app.primaryScreen()
            if screen is None:
                raise RuntimeError('No screen available for window test')
            area=screen.availableGeometry()
            if area.width() < 1 or area.height() < 1:
                raise RuntimeError('Screen reports invalid available geometry')
            for width,height in ((800,600),(1280,720),(1920,1080)):
                window.showNormal()
                window.resize(min(width,area.width()),min(height,area.height()))
                app.processEvents()
                if not window.isVisible() or window.isMinimized():
                    raise RuntimeError(f'Window became unusable at {width}x{height}')
            window.showMaximized()
            app.processEvents()
            if not window.isMaximized():
                raise RuntimeError('Window failed to maximize')
            window.showNormal()
            app.processEvents()
            if window.isMaximized() or window.isMinimized():
                raise RuntimeError('Window failed to leave maximized state')
            problems=bundled_resource_report()
            if problems:
                raise RuntimeError('; '.join(problems))
            window.hide()
            return 0
        except Exception as exc:
            print(f'GUI smoke test failed: {exc}', file=sys.stderr)
            return 1
    window=Suite();window.show();return app.exec()
if __name__=='__main__':sys.exit(main())
