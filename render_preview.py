import vtk

# Read STL
reader = vtk.vtkSTLReader()
reader.SetFileName("acme_c_bushing.stl")
reader.Update()

# Smooth normals for better shading
normals = vtk.vtkPolyDataNormals()
normals.SetInputConnection(reader.GetOutputPort())
normals.SetFeatureAngle(60)
normals.Update()

mapper = vtk.vtkPolyDataMapper()
mapper.SetInputConnection(normals.GetOutputPort())

actor = vtk.vtkActor()
actor.SetMapper(mapper)
actor.GetProperty().SetColor(0.75, 0.75, 0.78)   # aluminium
actor.GetProperty().SetSpecular(0.6)
actor.GetProperty().SetSpecularPower(40)
actor.GetProperty().SetAmbient(0.2)
actor.GetProperty().SetDiffuse(0.8)

renderer = vtk.vtkRenderer()
renderer.AddActor(actor)
renderer.SetBackground(0.15, 0.15, 0.18)
renderer.ResetCamera()

# Isometric-ish view
cam = renderer.GetActiveCamera()
cam.Elevation(20)
cam.Azimuth(45)
renderer.ResetCameraClippingRange()

# Two lights for depth
light1 = vtk.vtkLight()
light1.SetPosition(100, 100, 200)
light1.SetIntensity(1.0)
renderer.AddLight(light1)

light2 = vtk.vtkLight()
light2.SetPosition(-80, -50, 100)
light2.SetIntensity(0.4)
renderer.AddLight(light2)

rw = vtk.vtkRenderWindow()
rw.SetOffScreenRendering(1)
rw.AddRenderer(renderer)
rw.SetSize(900, 900)
rw.Render()

w2i = vtk.vtkWindowToImageFilter()
w2i.SetInput(rw)
w2i.Update()

writer = vtk.vtkPNGWriter()
writer.SetFileName("acme_c_bushing_preview.png")
writer.SetInputConnection(w2i.GetOutputPort())
writer.Write()
print("Saved acme_c_bushing_preview.png")
