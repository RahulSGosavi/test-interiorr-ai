import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { foldersAPI, filesAPI, projectsAPI } from '@/lib/api';
import useStore from '@/lib/store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ArrowLeft, FolderPlus, Upload, Folder, FileText, Trash2, FileSpreadsheet } from 'lucide-react';

const ProjectFiles = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [folders, setFolders] = useState([]);
  const [selectedFolder, setSelectedFolder] = useState(null);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newFolderName, setNewFolderName] = useState('');
  const [folderDialogOpen, setFolderDialogOpen] = useState(false);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    loadData();
  }, [projectId]);

  useEffect(() => {
    if (selectedFolder) {
      loadFiles(selectedFolder.id);
    }
  }, [selectedFolder]);

  const loadData = async () => {
    try {
      const [projectsRes, foldersRes] = await Promise.all([
        projectsAPI.getAll(),
        foldersAPI.getAll(projectId),
      ]);
      const proj = projectsRes.data.find((p) => p.id === projectId);
      setProject(proj);
      setFolders(foldersRes.data);
      if (foldersRes.data.length > 0) {
        setSelectedFolder(foldersRes.data[0]);
      }
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const loadFiles = async (folderId) => {
    try {
      const response = await filesAPI.getAll(folderId);
      setFiles(response.data);
    } catch (error) {
      toast.error('Failed to load files');
    }
  };

  const handleCreateFolder = async (e) => {
    e.preventDefault();
    if (!newFolderName.trim()) return;

    try {
      await foldersAPI.create(projectId, { name: newFolderName });
      toast.success('Folder created!');
      setNewFolderName('');
      setFolderDialogOpen(false);
      loadData();
    } catch (error) {
      toast.error('Failed to create folder');
    }
  };

  const handleUploadFile = async (e) => {
    e.preventDefault();
    if (!uploadFile || !selectedFolder) return;

    setUploading(true);
    try {
      await filesAPI.upload(selectedFolder.id, uploadFile);
      toast.success('File uploaded!');
      setUploadFile(null);
      setUploadDialogOpen(false);
      loadFiles(selectedFolder.id);
    } catch (error) {
      toast.error('Failed to upload file');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteFolder = async (id, name) => {
    if (!window.confirm(`Delete folder "${name}"?`)) return;

    try {
      await foldersAPI.delete(id);
      toast.success('Folder deleted');
      setSelectedFolder(null);
      loadData();
    } catch (error) {
      toast.error('Failed to delete folder');
    }
  };

  const handleDeleteFile = async (id, name) => {
    if (!window.confirm(`Delete file "${name}"?`)) return;

    try {
      await filesAPI.delete(id);
      toast.success('File deleted');
      loadFiles(selectedFolder.id);
    } catch (error) {
      toast.error('Failed to delete file');
    }
  };

  const getFileIcon = (fileType) => {
    if (fileType === 'pdf') return <FileText className="w-5 h-5" />;
    if (fileType === 'excel') return <FileSpreadsheet className="w-5 h-5" />;
    return <FileText className="w-5 h-5" />;
  };

  if (loading) {
    return <div className="min-h-screen h-screen w-full flex items-center justify-center">Loading...</div>;
  }

  return (
    <div className="min-h-screen h-screen w-full overflow-auto flex flex-col" style={{ background: 'linear-gradient(to bottom right, #f8fafc, #e0f2fe)' }}>
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10 flex-shrink-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <Button variant="ghost" onClick={() => navigate('/')} data-testid="back-button">
                <ArrowLeft className="w-5 h-5" />
              </Button>
              <div>
                <h1 className="text-2xl font-bold" data-testid="project-title">
                  {project?.name}
                </h1>
                <p className="text-sm text-gray-500">Manage files and folders</p>
              </div>
            </div>
            <div className="flex gap-2">
              <Dialog open={folderDialogOpen} onOpenChange={setFolderDialogOpen}>
                <DialogTrigger asChild>
                  <Button className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="create-folder-button">
                    <FolderPlus className="w-4 h-4 mr-2" />
                    New Folder
                  </Button>
                </DialogTrigger>
                <DialogContent className="bg-white">
                  <form onSubmit={handleCreateFolder}>
                    <DialogHeader>
                      <DialogTitle className="text-gray-900">Create New Folder</DialogTitle>
                      <DialogDescription className="text-gray-600">Organize your files with folders</DialogDescription>
                    </DialogHeader>
                    <div className="py-4">
                      <Label htmlFor="folderName" className="text-gray-700">Folder Name</Label>
                      <Input
                        id="folderName"
                        placeholder="e.g., Floor Plans"
                        value={newFolderName}
                        onChange={(e) => setNewFolderName(e.target.value)}
                        className="mt-2 bg-white border-gray-300"
                        data-testid="folder-name-input"
                      />
                    </div>
                    <DialogFooter>
                      <Button type="submit" className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="submit-create-folder">
                        Create Folder
                      </Button>
                    </DialogFooter>
                  </form>
                </DialogContent>
              </Dialog>
              <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
                <DialogTrigger asChild>
                  <Button 
                    disabled={!selectedFolder} 
                    className="bg-green-600 hover:bg-green-700 text-white disabled:bg-gray-400 disabled:text-gray-200"
                    data-testid="upload-file-button"
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    Upload File
                  </Button>
                </DialogTrigger>
                <DialogContent className="bg-white">
                  <form onSubmit={handleUploadFile}>
                    <DialogHeader>
                      <DialogTitle className="text-gray-900">Upload File</DialogTitle>
                      <DialogDescription className="text-gray-600">
                        Upload PDF or Excel files to {selectedFolder?.name}
                      </DialogDescription>
                    </DialogHeader>
                    <div className="py-4">
                      <Label htmlFor="file" className="text-gray-700 font-medium">Choose File</Label>
                      <Input
                        id="file"
                        type="file"
                        accept=".pdf,.xlsx,.xls,.csv"
                        onChange={(e) => setUploadFile(e.target.files[0])}
                        className="mt-2 bg-white border-gray-300 text-gray-900 cursor-pointer file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                        data-testid="file-input"
                      />
                      {uploadFile && (
                        <p className="text-sm text-green-600 font-medium mt-2 bg-green-50 px-3 py-2 rounded" data-testid="selected-file-name">
                          ✓ Selected: {uploadFile.name}
                        </p>
                      )}
                    </div>
                    <DialogFooter>
                      <Button 
                        type="submit" 
                        disabled={!uploadFile || uploading} 
                        className="bg-green-600 hover:bg-green-700 text-white disabled:bg-gray-400"
                        data-testid="submit-upload-file"
                      >
                        {uploading ? 'Uploading...' : 'Upload'}
                      </Button>
                    </DialogFooter>
                  </form>
                </DialogContent>
              </Dialog>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {folders.length === 0 ? (
          <div className="text-center py-12" data-testid="no-folders-message">
            <Folder className="w-16 h-16 mx-auto text-gray-400 mb-4" />
            <h3 className="text-xl font-semibold mb-2">No folders yet</h3>
            <p className="text-gray-500 mb-6">Create a folder to organize your files</p>
          </div>
        ) : (
          <Tabs value={selectedFolder?.id} onValueChange={(val) => {
            const folder = folders.find((f) => f.id === val);
            setSelectedFolder(folder);
          }}>
            <TabsList className="mb-6">
              {folders.map((folder) => (
                <TabsTrigger key={folder.id} value={folder.id} data-testid={`folder-tab-${folder.id}`}>
                  <Folder className="w-4 h-4 mr-2" />
                  {folder.name}
                </TabsTrigger>
              ))}
            </TabsList>

            {folders.map((folder) => (
              <TabsContent key={folder.id} value={folder.id}>
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-xl font-semibold" data-testid="folder-title">{folder.name}</h3>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeleteFolder(folder.id, folder.name)}
                    data-testid={`delete-folder-${folder.id}`}
                  >
                    <Trash2 className="w-4 h-4 text-red-500" />
                  </Button>
                </div>

                {files.length === 0 ? (
                  <div className="text-center py-12 bg-white rounded-lg" data-testid="no-files-message">
                    <FileText className="w-12 h-12 mx-auto text-gray-400 mb-4" />
                    <p className="text-gray-500">No files in this folder</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {files.map((file) => (
                      <Card
                        key={file.id}
                        className="card-hover cursor-pointer border-2 hover:border-blue-500"
                        onClick={() => navigate(`/file/${file.id}`)}
                        data-testid={`file-card-${file.id}`}
                      >
                        <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
                          <div className="flex items-center gap-2 flex-1 min-w-0">
                            <div className="flex-shrink-0">
                              {getFileIcon(file.file_type)}
                            </div>
                            <CardTitle className="text-base truncate" data-testid={`file-name-${file.id}`} title={file.name}>
                              {file.name}
                            </CardTitle>
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteFile(file.id, file.name);
                            }}
                            data-testid={`delete-file-${file.id}`}
                          >
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </Button>
                        </CardHeader>
                        <CardContent>
                          <div className="text-sm text-gray-500">
                            <p>Type: {file.file_type.toUpperCase()}</p>
                            {file.meta?.page_count && <p>Pages: {file.meta.page_count}</p>}
                            {file.meta?.sheet_count && <p>Sheets: {file.meta.sheet_count}</p>}
                            <p className="mt-2">
                              Uploaded {new Date(file.uploaded_at).toLocaleDateString()}
                            </p>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </TabsContent>
            ))}
          </Tabs>
        )}
      </main>
    </div>
  );
};

export default ProjectFiles;