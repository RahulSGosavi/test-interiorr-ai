import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { filesAPI } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowLeft, PenTool, Brain, MessageSquare, FileText, FileSpreadsheet } from 'lucide-react';
import { motion } from 'framer-motion';

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
      description: 'Draw, measure, and annotate with AutoCAD-level tools',
      icon: PenTool,
      color: 'from-blue-500 to-cyan-500',
      disabled: file?.file_type !== 'pdf',
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
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center gap-4">
            <Button variant="ghost" onClick={() => navigate(-1)} data-testid="back-button">
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div className="flex items-center gap-3">
              {file?.file_type === 'pdf' ? (
                <FileText className="w-8 h-8 text-blue-600" />
              ) : (
                <FileSpreadsheet className="w-8 h-8 text-green-600" />
              )}
              <div>
                <h1 className="text-2xl font-semibold" data-testid="file-title">
                  {file?.name}
                </h1>
                <p className="text-sm text-gray-500">Choose an action below</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h2 className="text-4xl text-center mb-4 font-semibold">
            What would you like to do?
          </h2>
          <p className="text-center text-gray-600 mb-12 text-lg">
            Select one of the powerful features below
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
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
                  <CardHeader>
                    <div
                      className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${option.color} flex items-center justify-center mb-4`}
                    >
                      <option.icon className="w-8 h-8 text-white" />
                    </div>
                    <CardTitle className="text-2xl font-semibold">
                      {option.title}
                    </CardTitle>
                    <CardDescription className="text-base mt-2">
                      {option.description}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {option.disabled && (
                      <p className="text-sm text-red-600 font-semibold bg-red-50 px-3 py-2 rounded" data-testid={`disabled-message-${option.id}`}>
                        Only available for PDF files
                      </p>
                    )}
                    {!option.disabled && (
                      <Button 
                        className="w-full mt-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold"
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
          <div className="mt-12 max-w-2xl mx-auto">
            <Card>
              <CardHeader>
                <CardTitle>File Information</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-gray-500">File Type</p>
                    <p className="font-medium" data-testid="file-type">{file?.file_type?.toUpperCase()}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Uploaded</p>
                    <p className="font-medium" data-testid="upload-date">
                      {new Date(file?.uploaded_at).toLocaleDateString()}
                    </p>
                  </div>
                  {file?.meta?.page_count && (
                    <div>
                      <p className="text-gray-500">Pages</p>
                      <p className="font-medium" data-testid="page-count">{file.meta.page_count}</p>
                    </div>
                  )}
                  {file?.meta?.sheet_count && (
                    <div>
                      <p className="text-gray-500">Sheets</p>
                      <p className="font-medium" data-testid="sheet-count">{file.meta.sheet_count}</p>
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