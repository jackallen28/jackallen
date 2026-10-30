from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.collections import Sequence_TDF_Label as TDF_LabelSequence
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.RWGltf import RWGltf_CafWriter
from OCP.collections import IndexedDataMap_TCollection_AsciiString_TCollection_AsciiString as TColStd_IndexedDataMapOfStringString
from OCP.Message import Message_ProgressRange
from OCP.TCollection import TCollection_AsciiString
from OCP.IFSelect import IFSelect_RetDone
app = XCAFApp_Application.GetApplication_s()
doc = TDocStd_Document(TCollection_ExtendedString("doc"))
app.NewDocument(TCollection_ExtendedString("MDTV-XCAF"), doc)
r = STEPCAFControl_Reader(); r.SetColorMode(True); r.SetNameMode(True)
assert r.ReadFile("board.step") == IFSelect_RetDone
assert r.Transfer(doc)
st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
seq = TDF_LabelSequence(); st.GetFreeShapes(seq)
for i in range(1, seq.Length()+1):
    BRepMesh_IncrementalMesh(st.GetShape_s(seq.Value(i)), 0.03, False, 0.3, True)
w = RWGltf_CafWriter(TCollection_AsciiString("board.glb"), True)
ok = w.Perform(doc, TColStd_IndexedDataMapOfStringString(), Message_ProgressRange())
print("glb written:", ok)
