"""Clip-local anonymous identities from aligned OpenCV SFace embeddings.

Embeddings live in memory only. This is not a named-person identification
service. Models are optional for offline installs; setup_speaker_models.py
fetches pinned weights. Missing/uncertain evidence creates a new identity.
"""
import os

import numpy as np


class IdentityRegistry:
    def __init__(self,threshold=.45,margin=.08):
        self.threshold,self.margin = threshold,margin
        self.features = []

    def assign(self,feature,exclude=()):
        if feature is None:
            self.features.append(None)
            return len(self.features)-1
        vector = np.asarray(feature,dtype=float).flatten()
        norm = np.linalg.norm(vector)
        if not np.isfinite(norm) or norm<1e-8:
            return self.assign(None,exclude)
        vector /= norm
        matches = sorted([(float(np.dot(vector,old)),i) for i,old in enumerate(self.features)
                          if old is not None and i not in exclude],reverse=True)
        if matches and matches[0][0]>=self.threshold and (len(matches)==1 or matches[0][0]-matches[1][0]>=self.margin):
            return matches[0][1]
        self.features.append(vector)
        return len(self.features)-1


class Embeddings:
    def __init__(self):
        import cv2
        directory = os.environ.get('SPEAKER_MODELS_DIR',os.path.join('.cache','speaker-models'))
        path = os.path.join(directory,'face_recognition_sface_2021dec.onnx')
        self.model = cv2.FaceRecognizerSF.create(path,'') if os.path.isfile(path) else None
        self.mesh = None

    def feature(self,frame,face):
        if self.model is None:
            return None
        import cv2
        import mediapipe as mp
        if self.mesh is None:
            self.mesh = mp.solutions.face_mesh.FaceMesh(static_image_mode=True,max_num_faces=1,
                                                       min_detection_confidence=.5)
        height,width = frame.shape[:2]
        x,y,w,h = face
        x0,y0 = max(0,int(x-w*.25)),max(0,int(y-h*.5))
        x1,y1 = min(width,int(x+w*1.25)),min(height,int(y+h*1.3))
        if x1<=x0 or y1<=y0:
            return None
        result = self.mesh.process(cv2.cvtColor(frame[y0:y1,x0:x1],cv2.COLOR_BGR2RGB))
        if not result.multi_face_landmarks:
            return None
        points = result.multi_face_landmarks[0].landmark
        coordinates = []
        # Right eye, left eye, nose, mouth right and left: OpenCV alignCrop's
        # five-landmark contract. Sort each symmetric pair by image x.
        eye = sorted([(points[i].x*(x1-x0)+x0,points[i].y*(y1-y0)+y0) for i in (33,263)])
        nose = (points[1].x*(x1-x0)+x0,points[1].y*(y1-y0)+y0)
        mouth = sorted([(points[i].x*(x1-x0)+x0,points[i].y*(y1-y0)+y0) for i in (61,291)])
        for p in [*eye,nose,*mouth]:
            coordinates.extend(p)
        detection = np.array([x,y,w,h,*coordinates,1.],dtype=np.float32)
        crop = self.model.alignCrop(frame,detection)
        return self.model.feature(crop).copy()

    def close(self):
        if self.mesh is not None:
            self.mesh.close()


def identify_shots(video,scenes,strategies,alternates,fps):
    """Return scene start -> identity IDs, including single-camera shots."""
    import cv2
    import main as m
    import split_layout
    extractor,registry = Embeddings(),IdentityRegistry()
    if extractor.model is None:
        print('   Speaker embedding weights unavailable; identities are shot-local. Run scripts/setup_speaker_models.py.')
    cap = cv2.VideoCapture(video)
    identities = {}
    try:
        for i,(start,end) in enumerate(scenes):
            if strategies[i] not in ('TRACK','ALTERNATE'):
                continue
            cap.set(cv2.CAP_PROP_POS_FRAMES,min(end-1,start+max(1,int(fps*.3))))
            ok,frame = cap.read()
            if not ok:
                continue
            faces = ([split_layout.as_box(c) for c in alternates[start][1]] if start in alternates
                     else [c['box'] for c in m.detect_face_candidates(frame)])
            if start not in alternates:
                faces = sorted(faces,key=lambda b:b[2]*b[3],reverse=True)[:1]
            ids = []
            for face in faces:
                ids.append(registry.assign(extractor.feature(frame,face),exclude=ids))
            identities[start] = ids
    finally:
        cap.release()
        extractor.close()
    return identities
