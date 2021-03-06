#!/usr/bin/env python
import argparse
import logging
import json
import re
from collections import defaultdict
from rest_client import RestClient
from server_utils import assert_mysql_uri, assert_mysql_db_uri

class HcClient(RestClient):
    
    def submit_job(self, db_uri, production_uri, compara_uri, staging_uri, live_uri, hc_names, hc_groups, data_files_path, email, tag):
        assert_mysql_db_uri(db_uri)
        assert_mysql_db_uri(production_uri)
        assert_mysql_db_uri(compara_uri)
        assert_mysql_uri(staging_uri)
        assert_mysql_uri(live_uri)
        logging.info("Submitting job")
        payload = {
            'db_uri':db_uri,
            'production_uri':production_uri,
            'compara_uri':compara_uri,
            'staging_uri':staging_uri,
            'live_uri':live_uri,
            'hc_names':hc_names,
            'hc_groups':hc_groups,
            'data_files_path':data_files_path,
            'email':email,
            'tag':tag
        }
        return RestClient.submit_job(self,payload)
    
    
    def list_jobs(self, output_file, pattern='.*', failure_only=False):
        logging.info("Finding jobs matching {}".format(pattern))
        r = super(HcClient, self).list_jobs()
        re_pattern = re.compile(pattern)
        output = []
        for job in r:    
            if 'db_uri' in job['input'].keys() and re_pattern.match(job['input']['db_uri']) and (failure_only == False or ('output' in job and job['output']['status'] == 'failed')):
                self.print_job(job, print_results=False, print_input=False)
            if 'output' in job:
                if failure_only == True:
                    job['output']['results'] = {k: v for k, v in job['output']['results'].items() if v['status'] == 'failed'}
                output.append(job)
        if output_file!= None:
            output_file.write(json.dumps(output))

    def collate_jobs(self, output_file, pattern='.*'):
        logging.info("Collating jobs using tag " + str(pattern))
        r = super(HcClient, self).list_jobs()  
        re_pattern = re.compile(pattern)
        output = defaultdict(list)
        for job in r:
            try:
                if re_pattern.match(job['input']['tag']) and ('output' in job and job['output']['status'] == 'failed'):
                    job_id = job['id']
                    logging.info("Found tag " + str(pattern) + " for job: " + str(job_id) )
                    for h,r in {k: v for k, v in job['output']['results'].iteritems() if v['status'] == 'failed'}.items():
                        [output[h].append(job['input']['db_uri']+"\t"+m) for m in r['messages']]
            except:
                pass
        if output_file!= None:
            output_file.write(json.dumps(output))
    
    def print_job(self, job, print_results=False, print_input=False):
        logging.info("Job %s (%s) - %s" % (job['id'], job['input']['db_uri'], job['status']))
        if print_input == True:
            self.print_inputs(job['input'])
        if job['status'] == 'complete':
            if print_results == True:
                logging.info("HC result: " + str(job['output']['status']))
                for (hc, result) in job['output']['results'].iteritems():
                    logging.info("%s : %s" % (hc, result['status']))
                    if result['messages'] != None:
                        for msg in result['messages']:
                            logging.info(msg)
        elif job['status'] == 'incomplete':
            if print_results == True:
                logging.info("HC result: " + str(job['status']))
                logging.info(str(job['progress']['complete'])+"/"+str(job['progress']['total'])+" job complete")
        elif job['status'] == 'failed':
            failures = self.retrieve_job_failure(job['id'])
            logging.info("Job failed with error: "+ str(failures))
        else:
            raise ValueError("Unknown status {}".format(job['status']))

    def print_inputs(self,i):
        logging.info("DB URI: " + i['db_uri'])
        logging.info("Staging URI: " + i['staging_uri'])
        logging.info("Live URI: " + i['live_uri'])
        logging.info("Compara URI: " + i['compara_uri'])
        logging.info("Production URI: " + i['production_uri'])
        logging.info("Data files path: " + i['data_files_path'])
        if 'hc_names' in i:
            for hc in i['hc_names']:
                logging.info("HC: " + hc)
        if 'hc_groups' in i:
            for hc in i['hc_groups']:
                logging.info("HC: " + hc)
        if 'email' in i:
            logging.info("Email: " + i['email'])
        if 'tag' in i:
            logging.info("Tag: " + i['tag'])

if __name__ == '__main__':
            
    parser = argparse.ArgumentParser(description='Run HCs via a REST service')

    parser.add_argument('-u', '--uri', help='HC REST service URI', required=True)
    parser.add_argument('-a', '--action', help='Action to take', choices=['submit', 'retrieve', 'list', 'delete', 'collate'], required=True)
    parser.add_argument('-i', '--job_id', help='HC job identifier to retrieve')
    parser.add_argument('-v', '--verbose', help='Verbose output', action='store_true')
    parser.add_argument('-o', '--output_file', help='File to write output as JSON', type=argparse.FileType('w'))
    parser.add_argument('-d', '--db_uri', help='URI of database to test')
    parser.add_argument('-p', '--production_uri', help='URI of production database')
    parser.add_argument('-c', '--compara_uri', help='URI of compara master database')
    parser.add_argument('-s', '--staging_uri', help='URI of current staging server')
    parser.add_argument('-l', '--live_uri', help='URI of live server for comparison')
    parser.add_argument('-dfp', '--data_files_path', help='Data files path')
    parser.add_argument('-n', '--hc_names', help='List of healthcheck names to run', nargs='*')
    parser.add_argument('-g', '--hc_groups', help='List of healthcheck groups to run', nargs='*')
    parser.add_argument('-r', '--db_pattern', help='Pattern of DB URIs to restrict by', default='.*')
    parser.add_argument('-f', '--failure_only', help='Show failures only', action='store_true')
    parser.add_argument('-e', '--email', help='User email')
    parser.add_argument('-t', '--tag', help='Tag use to collate result and facilitate filtering')

    args = parser.parse_args()
    
    if args.verbose == True:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s - %(message)s')
    
    if args.uri.endswith('/') == False:
        args.uri = args.uri + '/'    

    client = HcClient(args.uri)
            
    if args.action == 'submit':
        job_id = client.submit_job(args.db_uri, args.production_uri, args.compara_uri, args.staging_uri, args.live_uri, args.hc_names, args.hc_groups, args.data_files_path, args.email, args.tag)
        logging.info('Job submitted with ID '+str(job_id))
    
    elif args.action == 'retrieve':
        job = client.retrieve_job(args.job_id)
        client.print_job(job, print_results=True, print_input=True)
    
    elif args.action == 'list':
        jobs = client.list_jobs(args.output_file, args.db_pattern, args.failure_only)   

    elif args.action == 'collate':
        if args.tag == None:
            raise ValueError("Collate needs a tag argument")
        jobs = client.collate_jobs(args.output_file, args.tag)   
    
    elif args.action == 'delete':
        client.delete_job(args.job_id)
        
