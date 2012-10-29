import os
import sys
import shutil

from utils.report import Report
from utils.parameters import Parameters
from utils.cisis import CISIS, IDFile
from utils.json2id import JSON2IDFile
from utils.files_uploaded_manager import UploadedFilesManager

from xml2json_converter import XML2JSONConverter
from json2id_article import JSON2IDFile_Article
from json_article import JSON_Article
from journal_issue_article import JournalList, JournalIssues, Journal, Section
from xml_files_set import XMLFilesSet
from xml_folders_set import XMLFoldersSet

from utils.img_converter import ImageConverter
from utils.email_service import EmailService

class DB_ISSUE:
    def __init__(self):
        pass

    def save_issue_id_in_proc_folder(self, id_filename, acron, issue_name):
        fname = self.xml_folders.id_folder + '/' + acron + issue_name + '.id'
        if os.path.exists(fname):
            os.unlink(fname)
        shutil.copyfile(id_filename, fname)

    def db2json(self, db):
        from tempfile import mkstemp
        import os
        r = []
        if os.path.exists(db + '.mst'):
            _, f = mkstemp()
            self.cisis.i2id(db, f)
            r = IDFile(f).id2json()
            os.remove(f)
        return r

    def load_issues(self, journals, issue_db_filename, issues_list = None):
        
        json_issues = self.db2json(issue_db_filename)
        if issues_list == None:
            issues_list = JournalIssues()
        
        for json_issue in json_issues:
            if '130' in json_issue:
                test = json_issue['130']
            else:
                test = json_issue['100']

            j = journals.find_journal(test)
            
            if j != None:
                issue = self.json_article.return_issue(json_issue, j)
                issue.json_data = json_issue
                issues_list.insert(issue, False)
        return issues_list
        
    def load_journals(self, title_db_filename, journal_list = None):
        json = self.db2json(title_db_filename)
        if journal_list == None:
            journal_list = JournalList()
        
        for json_item in json:
            j = Journal(json_item['100'], json_item['400'], json_item['68'])
            print(j.title + ' ' + j.issn_id)
            journal_list.insert(j, False)
        return journal_list

        
    def load_journal_titles_list(self, title_db_filename, journal_titles_list = []):
        json_titles = self.db2json(title_db_filename)
        
        for json_title in json_titles:
            if '100' in json_title:
                if not json_title['100'] in journal_titles_list:
                    journal_titles_list.append(json_title['100'])
        return journal_titles_list

    def create_proc_title_db(self, original_title_db_filenames, selected_journal_titles, selected_titles_db_filename):
        json_titles = []
        for item in original_title_db_filenames:
            json_titles += self.db2json(original_title_db_filenames)
        

        selected_journals = []
        for json_title in json_titles:
            if '100' in json_title:
                if json_title['100'] in selected_journal_titles:
                    selected_journals.append(json_title)

        from tempfile import mkstemp
        import os
        _, temp_title_id_filename = mkstemp()
                    
        JSON2IDFile(temp_title_id_filename, self.report).format_and_save_document_data(selected_journals)   
        self.cisis.id2i(temp_title_id_filename, selected_titles_db_filename)
        os.remove(temp_title_id_filename)
        

    def create_proc_issue_db(self, i_records_path, proc_issue_db_filename):
        self.cisis.create('null count=0', proc_issue_db_filename)
        for f in os.listdir(i_records_path):
            self.cisis.id2mst(i_records_path + '/' + f, proc_issue_db_filename, False)


class DBSet:
    def __init__(self, config):
        self.config = config 
        self.db_title_filenames = self.config.parameters['DB_TITLE_FILENAME']
        self.proc_title_db = self.config.parameters['PROC_DB_TITLE_FILENAME']
        
        self.db_issue_filenames = self.config.parameters['DB_ISSUE_FILENAME']
        self.proc_issue_db = self.config.parameters['PROC_DB_ISSUE_FILENAME']
        
        self.temp_proc_title_db_filename = self.config.parameters['TEMP_PROC_DB_TITLE_FILENAME']
        self.temp_proc_issue_db_filename = self.config.parameters['TEMP_PROC_DB_ISSUE_FILENAME']

        self.i_records_path = self.config.parameters['PATH_I_RECORD']
        
    def load(self):
        self.registered_journals = JournalList()
        for db in self.db_title_filenames:
            self.registered_journals = DB().load_journals(db, self.registered_journals)
        
        # load journal titles which are in proc
        self.inproc_journal_titles = DB().load_journal_titles_list(self.temp_proc_title_db_filename)

        # load data of all the issues registered in issue database
        self.registered_issues = JournalIssues()
        for db in db_issue_filenames:
            self.registered_issues = DB().load_issues(self.registered_journals, db, self.registered_issues)

        self.notregistered_issues = DB().load_issues(self.registered_journals, 'new_issues')
        
    def generate_db_for_proc(self, selected_journal_titles):
        DB().create_proc_issue_db(self.i_records_path, self.temp_proc_issue_db_filename)
        DB().create_proc_title_db(self.db_title_filenames, selected_journal_titles, self.temp_proc_title_db_filename)



class PMCXML2ISIS:

    def __init__(self, config, report, debug_report, debug = False):
        self.config = config 
        self.report = report
        self.debug_report = debug_report
        

        self.records_order = 'ohflc'
        self.cisis = CISIS(config.parameters['CISIS_PATH'])
        
        self.registered_journals = JournalList()
        self.registered_issues = JournalIssues()
        self.not_registered_issues = JournalIssues()

        # issues of this processing
        self.inproc_issues = JournalIssues()

        # journals of this processing
        self.inproc_journals = []
        
        self.not_registered_issues_db = 'new_issues'
        
        self.xml_folders = XMLFoldersSet(serial_archive_path, server_serial_path, web_img_path, web_pdf_path, web_xml_path, server_serial_path + '/scilista.lst')

        self.img_converter = ImageConverter()
        self.xml2json_converter = XML2JSONConverter('inputs/_pmcxml2isis.txt', debug_report, debug)
        self.json_article = JSON_Article(debug_report, report)
        self.email_service = EmailService(config.parameters['SENDER_EMAIL'])

    def process_data(self):

        db_set = DBSet(self.config)
        db_set.load()

        

        inproc_path, work_path, report_path = self.config.parameters['IN_PROC_PATH'], self.config.parameters['WORK_PATH'], self.config.parameters['REPORT_PATH']


        
        
        # process the package of XML files. Each package file is a compressed file and must contains all the articles of an issue
        email_config = [ p for k,p in self.config.parameters.items() if 'EMAIL' in k ]
        process_packages(inproc_path, work_path, report_path, email_config)


        
        

    def return_issue_to_compare(self, issue):
        
        found = self.inproc_issues.get(issue.id)
        if found == None:
            # issue is registered
            found = self.registered_issues.get(issue.id)
            if found == None:
                # issue is in new_issues
                found = self.not_registered_issues.get(issue.id)
                if found == None:
                    found = self.inproc_issues.insert(issue, False)
                    found.status = 'not_registered'
                else:
                    found = self.inproc_issues.insert(issue, False)
                    found.status = 'new_issues'
            else:
                found = self.inproc_issues.insert(issue, False)
                found.status = 'registered'

        
        return found

    def write_report_package(self, report_package, message, is_summary, is_error, display_on_screen = False, error_data = None):
        self.report.write(message, is_summary, is_error, display_on_screen, error_data)
        report_package.write(message, is_summary, is_error, False, error_data)
        


    def generate_id_files(self, report_package, package_file, work_path):
        files = os.listdir(work_path)
        xml_list = [ f for f in files if f.endswith('.XML') ]
        if len(xml_list)>0:
            self.write_report_package(report_package, 'Program will convert .XML to .xml', True, False, False)
            for f in xml_list:
                new_name = work_path +'/' + f.replace('.XML','.xml')
                shutil.copyfile(work_path+'/'+f, new_name)
                if os.path.exists(new_name):
                    self.write_report_package(report_package, 'Converted ' + new_name, True, False, False)
                    os.unlink(work_path+'/'+f)
                else:
                    self.write_report_package(report_package, 'Unable to convert ' + new_name, True, False, False)

        files = os.listdir(work_path)
        xml_list = [ f for f in files if f.endswith('.xml') ]
        issues = {}
        self.img_converter.img_to_jpeg(work_path, work_path)

        files_set_list = {}
        files_set = None
        
        self.write_report_package(report_package, 'XML Files: ' + str(len(xml_list)), True, True, True)
        if len(xml_list) == 0:
            self.write_report_package(report_package, 'All the files in the package: ' + '\n' + '\n'.join(files), False, True, False)
        for f in xml_list:
            xml_filename = work_path + '/' + f
            
            self.write_report_package(report_package, '\n' + '-' * 80 + '\n' + 'File: ' + f, True, True, True)

            json_data = self.xml2json_converter.convert(xml_filename, report_package)
            issue = None

            if type(json_data) == type({}):
                files = os.listdir(work_path)
                img_files = [ img_file[0:img_file.rfind('.')] for img_file in files if img_file.startswith(f.replace('.xml', '-'))  ]
                img_files = list(set(img_files))

                article = self.json_article.return_article(json_data, img_files, self.registered_journals, xml_filename, report_package)
                if article != None:
                    issue_to_compare = self.return_issue_to_compare(article.issue)
                    issue_errors = article.issue.is_valid(issue_to_compare)

                    warnings = []
                    if len(issue_errors) == 0:
                        issue = article.issue
                    
                        journal_folder = issue.journal.acron
                        issue_folder = issue.name 
                        db_name = issue.name
            
                        if journal_folder + db_name in files_set_list.keys():
                            files_set = files_set_list[journal_folder + db_name]
                        else:
                            files_set = XMLFilesSet(self.xml_folders, journal_folder, issue_folder, db_name)
                            files_set_list[journal_folder + db_name] = files_set

                        self.write_report_package(report_package, ' => ' + article.issue.journal.title + ' ' + article.issue.name + ' ' + article.page, True, False, False)

                        if not article.issue.journal.title in self.inproc_journals:
                            self.inproc_journals.append(article.issue.journal.title)

                        section = issue_to_compare.toc.insert(Section(article.section_title), False)
                        article.issue = issue_to_compare
                        issue_to_compare.articles.insert(article, True)
                        issues[article.issue.journal.acron + article.issue.name] = issue_to_compare

                        self.generate_id_file(report_package, article, files_set)
                    else:
                        self.write_report_package(report_package, ' ! ERROR: Invalid issue data of ' + xml_filename, True, True, True)
                        for err in issue_errors:
                            self.write_report_package(report_package, err, True, True, True)

                else:
                    self.write_report_package(report_package, ' ! ERROR: Invalid xml ' + xml_filename, True, True, True)

        
        for key, issue in issues.items():
            files_set = files_set_list[key]

            files_set.archive_package_file(package_file)
            self.generate_db(report_package, issue, files_set)
            self.xml_folders.add_to_scilista(issue.journal.acron, issue.name)

            files = os.listdir(work_path)
            if len(files)>0:
                for file in files:
                    files_set.move_file_to_path(work_path + '/' + file, files_set.extracted_package_path)
            files = os.listdir(work_path)
            if len(files) == 0:
                self.write_report_package(report_package, ' Deleting ' + work_path, True, False, True)
                shutil.rmtree(work_path)
        


        if len(issues) > 1:
            self.write_report_package(report_package, ' ! ERROR: This package contains data of more than one issue:' + ','.join(issues.keys()), True, True, True)


    def generate_id_file(self, report_package, article, files_set):
        #, serial_archive_path, server_serial_path, img_path, pdf_path, xml_path
        
        id_filename = os.path.basename(article.xml_filename.replace('.xml', '.id'))
    
        id_file = JSON2IDFile_Article(files_set.id_path + '/' + id_filename, self.report)
        id_file.format_and_save_document_data(article.json_data, self.records_order, files_set.db_name, files_set.xml_filename(article.xml_filename))
        
        
        files_set.archive(article.xml_filename)


    def generate_db(self, report_package, issue, files_set):
        
        self.write_report_package(report_package, '\n' + '-' * 80 + '\n' + 'Generating db ' + files_set.serial_path + ' ' + issue.name, True, False, True )
        
        files_set.delete_db()
        

        id_file = JSON2IDFile(files_set.id_path + '/i.id', report)
        issue.json_data['122'] = str(len(issue.articles.elements))
        issue.json_data['49'] = issue.toc.return_json()

        id_file.format_and_save_document_data(issue.json_data)
    
        self.save_issue_id_in_proc_folder(files_set.id_path + '/i.id', issue.journal.acron, issue.name)

        self.cisis.id2mst(files_set.id_path + '/i.id', files_set.db_filename, True)
        if issue.status == 'not_registered':
            self.cisis.append(files_set.db_filename, self.not_registered_issues_db)

        list = os.listdir(files_set.id_path)
        articles_id = [ f for f in list if '.id' in f and  f != 'i.id' ]
        
        
        self.write_report_package(report_package, ' Total of xml files: ' + str(len(issue.articles.elements)), True, False, False )
        self.write_report_package(report_package, ' Total of id files: ' + str(len(articles_id)) , True, False, False  )
        self.write_report_package(report_package, ' Status of ' + issue.journal.acron +  ' ' + issue.name  + ': ' + issue.status, True, False, False  )
        


        if len(issue.articles.elements) != len(articles_id):
            self.write_report_package(report_package, ' ! WARNING: Check total of xml files and id files', True, True, True )
        
        if issue.status == 'not_registered':
            self.write_report_package(report_package, "\n" + ' ! WARNING: New issue '  + issue.journal.acron +  ' ' + issue.name  + "\n" , True, True, True )
        for f in articles_id:        
            self.cisis.id2mst(files_set.id_path + '/' + f, files_set.db_filename, False)

    def process_packages(self, package_path, work_path, report_path, email_data):
        for filename in os.listdir(package_path):
            package_file = package_path + '/' + filename
            self.process_package(package_file, work_path, report_path, email_data)

    def process_package(self, package_file, work_path, report_path, email_data):
        package_path = os.path.dirname(package_file)
        folder = os.path.basename(package_file)
        folder = folder[0:folder.rfind('.')]

        work_path += '/' + folder 


        files = ['detailed.log', 'error.log', 'summarized.txt'] 
        log_filename, err_filename, summary_filename = [ report_path + '/' +  folder + '_' + f for f in files ]
        report_package = Report(log_filename, err_filename, summary_filename, 0, False) 

        self.write_report_package(report_package, '\n' +'=' * 80 + '\n' +  'Package: ' + os.path.basename(package_file), True, False, True )
        

        uploaded_files_manager = UploadedFilesManager(report_package, package_path)
        uploaded_files_manager.extract_file(package_file, work_path)
        uploaded_files_manager.backup(package_file)

        emails = ''
        package_name = os.path.basename(package_file)
        if os.path.exists(work_path + '/email.txt'):
            f = open(work_path + '/email.txt', 'r')
            emails = f.read()
            f.close()

        self.generate_id_files(report_package, package_file, work_path)
        
        self.send_email(email_data, emails, package_name, [summary_filename,err_filename, ])

    def send_email(self, email_data, emails, package_name, report_files):        
        emails = emails.replace(';', ',')
        

        if email_data['FLAG_SEND_EMAIL_TO_XML_PROVIDER'] == 'yes':
            to = emails.split(',')
            text = ''
            bcc = email_data['BCC_EMAIL']
        else:

            to = email_data['BCC_EMAIL']
            if len(emails) > 0:
                foward_to = emails
            else:
                foward_to = '(e-mail ausente no pacote)'
            text = email_data['ALERT_FORWARD'] + ' ' +  foward_to + '\n'  + '-' * 80 + '\n\n'
            bcc = []

        if len(email_data['EMAIL_TEXT']) > 0:
            if os.path.isfile(email_data['EMAIL_TEXT']):
                f = open(email_data['EMAIL_TEXT'], 'r')
                text += f.read()
                f.close()

                text = text.replace('REPLACE_PACKAGE', package_name)

        attached_files = [ item for item in report_files if os.path.exists(item) ]
        if email_data['FLAG_ATTACH_REPORTS'] == 'yes':
            text = text.replace('REPLACE_ATTACHED_OR_BELOW', 'em anexo')

        else:
            text = text.replace('REPLACE_ATTACHED_OR_BELOW', 'abaixo')
            
            for item in attached_files:
                
                f = open(item, 'r')
                text += '-'* 80 + '\n'+ f.read() + '-'* 80 + '\n' 
                f.close()
            attached_files = []

        self.report.write('Email data:' + package_name)
        self.report.write('to:' + ','.join(to))
        self.report.write('bcc:' + ','.join(bcc))
        self.report.write('files:' + ','.join(attached_files))
        self.report.write('text:' + text)

        if email_data['IS_AVAILABLE_EMAIL_SERVICE'] == 'yes':
            self.email_service.send(to, [], email_data['BCC_EMAIL'], email_data['EMAIL_SUBJECT_PREFIX'] + package_name, text, attached_files)

    def download(self, server, user, pasw, folder, ftp_path, queue_path, report_ftp):      
        print('Before downloading - files in ' + ftp_path)
        report_ftp.write('Files in ' + ftp_path, True)
        for f in os.listdir(ftp_path):
            report_ftp.write(f, True)

        
        report_ftp.write('Downloading...', True, False, True)

        MyFTP(report_ftp, server, user, pasw).download_files(ftp_path, folder)

        print('After downloading - files in ' + ftp_path)
        for f in os.listdir(ftp_path):
            report_ftp.write(f, True)
    
        uploaded_files_manager = UploadedFilesManager(report, ftp_path)
        uploaded_files_manager.transfer_files(queue_path)

        print('Downloaded files in ' + queue_path)
        for f in os.listdir(queue_path):
            report_ftp.write(f, True, False, True)
    
        print('Read '+ report_ftp.summary_filename)
        print('finished')

if __name__ == '__main__':
    # read configuration data
    from utils.configuration import Configuration

    #config_parameters = [ 'EMAIL_SUBJECT_PREFIX', 'PROC_DB_TITLE_FILENAME', 'PROC_DB_ISSUE_FILENAME', 'DB_TITLE_FILENAME', 'FTP_SERVER',  'FTP_USER', 'FTP_PSWD',  'FTP_DIR', 'FLAG_ATTACH_REPORTS', 'ALERT_FORWARD', 'IS_AVAILABLE_EMAIL_SERVICE', 'EMAIL_TEXT', 'SENDER_EMAIL', 'BCC_EMAIL', 'FLAG_SEND_EMAIL_TO_XML_PROVIDER', 'DB_ISSUE_FILENAME', 'FTP_PATH', 'QUEUE_PATH', 'IN_PROC_PATH',  'WORK_PATH', 'TRASH_PATH', 'SERIAL_ARCHIVE_PATH', 'SERIAL_PROC_PATH', 'PDF_PATH', 'IMG_PATH', 'XML_PATH', 'CISIS_PATH', 'LOG_FILENAME', 'ERROR_FILENAME', 'SUMMARY_REPORT', 'DEBUG_DEPTH', 'DISPLAY_MESSAGES_ON_SCREEN']
    config = Configuration()
    #error, msg = conf.check(config_parameters)
    #print('\n'.join(msg))

    required_config = ['REPORT_PATH',  'LOG_FILENAME', 'ERROR_FILENAME', 'SUMMARY_REPORT', 'DEBUG_DEPTH', 'DISPLAY_MESSAGES_ON_SCREEN']
    error, msg = config.check(required_config)

    if error:
        print('Missing FTP data')
        print( '\n'.join())
    

    what_to_do = ''
    if not error:
        from datetime import date
        
        # read parameters of execution 
        parameter_list = ['script', 'operation = ftp (to download the packages from ftp)|  process (to process the packages)' ]         
        parameters = Parameters(parameter_list)
        if parameters.check_parameters(sys.argv):
            script_name, what_to_do = sys.argv
        else:
            what_to_do = 'process'

        

    if what_to_do != '':
        # ===============================
        # REPORTS
        # ===============================
        report_path = config.parameters['REPORT_PATH'] + date.today().isoformat()
        if not os.path.exists(report_path):
            os.makedirs(report_path)
        
        log_filename = config.parameters['LOG_FILENAME']
        err_filename = config.parameters['ERROR_FILENAME']
        summary_filename = config.parameters['SUMMARY_REPORT']
        files = [ log_filename, err_filename, summary_filename]
        
        debug_depth = config.parameters['DEBUG_DEPTH']
        display_on_screen = config.parameters['DISPLAY_MESSAGES_ON_SCREEN']

        debug_log_filename, debug_err_filename, debug_summary_filename =  [ report_path + '/debug_' + f for f in files ]
        debug_report = Report(debug_log_filename, debug_err_filename, debug_summary_filename, int(debug_depth), (display_on_screen == 'yes')) 
        
        log_filename, err_filename, summary_filename = [ report_path + '/' + f for f in files ]
        report = Report(log_filename, err_filename, summary_filename, int(debug_depth), (display_on_screen == 'yes')) 
        
        # ===============================
        
        
        
        
        

    if what_to_do == 'process':
        # Load XML data into ISIS Database
        
        # Move files from ftp_path to inproc_path
        uploaded_files_manager = UploadedFilesManager(report, config.parameters['QUEUE_PATH'])
        uploaded_files_manager.transfer_files(config.parameters['INPROC_PATH'])

        db_manager = DB()

        #db_manager.load_data_from_db()
        #pmcxml2isis = PMCXML2ISIS('ohflc', 'inputs/_pmcxml2isis.txt', CISIS(cisis_path), xml_folders, EmailService(email_data['SENDER_EMAIL']), report, debug_report)
        pmcxml2isis = PMCXML2ISIS(config, report, debug_report)
        pmcxml2isis.process_data(config.parameters['INPROC_PATH'], config.parameters['REPORT_PATH'])

        #db_manager.generate_base_for_proc()


        print('-' * 80)
        print('Check report files:  ')
        print('Errors report: ' + err_filename)
        print('Summarized report: ' + summary_filename)
        
        print('Detailed report: ' + log_filename)
        print('Reports for each package of XML files in ' + work_path)

    elif what_to_do == 'ftp':
        # baixar do servidor de ftp e apagar de la
        # TODO
        from utils.my_ftp import MyFTP

        log_filename, err_filename, summary_filename = [ report_path + '/ftp_' + f for f in files ]
        report_ftp = Report(log_filename, err_filename, summary_filename, int(debug_depth), (display_on_screen == 'yes')) 
        
        required_config = ['FTP_SERVER',  'FTP_USER', 'FTP_PSWD',  'FTP_DIR', 'FTP_PATH', 'QUEUE_PATH']
        error, msg = config.check(required_config)

        if error:
            print('Missing FTP data')
            print( '\n'.join())
        else:
            server, user, pasw, folder = config.parameters['FTP_SERVER'], config.parameters['FTP_USER'], config.parameters['FTP_PSWD'], config.parameters['FTP_DIR']
            pmcxml2isis.download(self, server, user, pasw, folder, config.parameters['FTP_PATH'], config.parameters['QUEUE_PATH'], report_ftp)
    
        
        
    
    