import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { filesAPI } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowLeft, PenTool, Brain, MessageSquare, FileText, FileSpreadsheet } from 'lucide-react';
import { motion } from 'framer-motion';

// Helper function to check if a file can be annotated
const canAnnotate = (file) => {
  if (!file) return false;
  const fileType = file.file_type?.toLowerCase() || '';
  const fileName = file.name?.toLowerCase() || '';
  
  // Allow PDFs
  if (fileType === 'pdf' || fileName.endsWith('.pdf')) return true;
  
  // Allow images
  const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'];
  const imageMimeTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp'];
  const ext = fileName.substring(fileName.lastIndexOf('.'));
  
  return imageExtensions.includes(ext) || imageMimeTypes.includes(fileType);
};

const FileMainOptions = () => {
  const { fileId } = useParams();
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadFile();
  }, [fileId]);

  const loadFile = async () => {
    try {
      const response = await filesAPI.getOne(fileId);
      setFile(response.data);
    } catch (error) {
      toast.error('Failed to load file');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="min-h-screen h-screen w-full flex items-center justify-center">Loading...</div>;
  }

  const options = [
    {
      id: 'annotation',
      title: 'Annotation',
      description: 'Draw, measure, and annotate with AutoCAD-level tools (PDF & Images)',
      icon: PenTool,
      color: 'from-blue-500 to-cyan-500',
      disabled: !canAnnotate(file),
      route: `/file/${fileId}/annotate`,
    },
    {
      id: 'pricing-ai',
      title: 'Pricing AI Assistant',
      description: 'Ask questions about costs, codes, and calculations',
      icon: Brain,
      color: 'from-purple-500 to-pink-500',
      disabled: false,
      route: `/file/${fileId}/pricing-ai`,
    },
    {
      id: 'discussion',
      title: 'Discussion',
      description: 'Collaborate with team members in real-time',
      icon: MessageSquare,
      color: 'from-green-500 to-teal-500',
      disabled: false,
      route: `/file/${fileId}/discussion`,
    },
  ];

  return (
    <div className="min-h-screen h-screen w-full overflow-auto flex flex-col" style={{ background: 'linear-gradient(to bottom right, #f8fafc, #e0f2fe, #fae8ff)' }}>
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10 flex-shrink-0">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 lg:px-6 py-2 sm:py-3">
          <div className="flex items-center gap-2 sm:gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate(-1)} data-testid="back-button" className="h-7 w-7 p-0">
              <ArrowLeft className="w-3.5 h-3.5" />
            </Button>
            <div className="flex items-center gap-2">
              {file?.file_type === 'pdf' ? (
                <FileText className="w-5 h-5 sm:w-6 sm:h-6 text-blue-600" />
              ) : (
                <FileSpreadsheet className="w-5 h-5 sm:w-6 sm:h-6 text-green-600" />
              )}
              <div>
                <h1 className="text-sm sm:text-base font-semibold truncate max-w-[200px] sm:max-w-none" data-testid="file-title">
                  {file?.name}
                </h1>
                <p className="text-[10px] sm:text-xs text-gray-500">Choose an action below</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-3 sm:px-4 lg:px-6 py-6 sm:py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h2 className="text-xl sm:text-2xl lg:text-3xl text-center mb-3 sm:mb-4 font-semibold">
            What would you like to do?
          </h2>
          <p className="text-center text-gray-600 mb-6 sm:mb-8 text-xs sm:text-sm lg:text-base">
            Select one of the powerful features below
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6 max-w-6xl mx-auto">
            {options.map((option, index) => (
              <motion.div
                key={option.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
              >
                <Card
                  className={`h-full border-2 transition-all duration-300 ${
                    option.disabled
                      ? 'opacity-50 cursor-not-allowed'
                      : 'cursor-pointer hover:shadow-2xl hover:scale-105'
                  }`}
                  onClick={() => !option.disabled && navigate(option.route)}
                  data-testid={`option-card-${option.id}`}
                >
                  <CardHeader className="p-4 sm:p-5">
                    <div
                      className={`w-10 h-10 sm:w-12 sm:h-12 rounded-xl bg-gradient-to-br ${option.color} flex items-center justify-center mb-2 sm:mb-3`}
                    >
                      <option.icon className="w-5 h-5 sm:w-6 sm:h-6 text-white" />
                    </div>
                    <CardTitle className="text-base sm:text-lg font-semibold">
                      {option.title}
                    </CardTitle>
                    <CardDescription className="text-xs sm:text-sm mt-1 sm:mt-1.5">
                      {option.description}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-4 sm:p-5 pt-0">
                    {option.disabled && (
                      <p className="text-[10px] sm:text-xs text-red-600 font-semibold bg-red-50 px-2 py-1.5 rounded" data-testid={`disabled-message-${option.id}`}>
                        Only available for PDF and image files
                      </p>
                    )}
                    {!option.disabled && (
                      <Button 
                        className="w-full mt-2 h-8 sm:h-9 text-xs sm:text-sm bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold"
                        data-testid={`open-${option.id}-button`}
                      >
                        Open →
                      </Button>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>

          {/* File Info */}
          <div className="mt-6 sm:mt-8 max-w-2xl mx-auto">
            <Card>
              <CardHeader className="p-3 sm:p-4">
                <CardTitle className="text-sm sm:text-base">File Information</CardTitle>
              </CardHeader>
              <CardContent className="p-3 sm:p-4 pt-0">
                <div className="grid grid-cols-2 gap-3 sm:gap-4 text-xs sm:text-sm">
                  <div>
                    <p className="text-gray-500 text-[10px] sm:text-xs">File Type</p>
                    <p className="font-medium text-xs sm:text-sm" data-testid="file-type">{file?.file_type?.toUpperCase()}</p>
                  </div>
                  <div>
                    <p className="text-gray-500 text-[10px] sm:text-xs">Uploaded</p>
                    <p className="font-medium text-xs sm:text-sm" data-testid="upload-date">
                      {new Date(file?.uploaded_at).toLocaleDateString()}
                    </p>
                  </div>
                  {file?.meta?.page_count && (
                    <div>
                      <p className="text-gray-500 text-[10px] sm:text-xs">Pages</p>
                      <p className="font-medium text-xs sm:text-sm" data-testid="page-count">{file.meta.page_count}</p>
                    </div>
                  )}
                  {file?.meta?.sheet_count && (
                    <div>
                      <p className="text-gray-500 text-[10px] sm:text-xs">Sheets</p>
                      <p className="font-medium text-xs sm:text-sm" data-testid="sheet-count">{file.meta.sheet_count}</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </motion.div>
      </main>
    </div>
  );
};

export default FileMainOptions;