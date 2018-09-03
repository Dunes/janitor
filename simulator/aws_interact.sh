#!/usr/bin/env bash

action=$1
url_file=$2

repo_dir=/home/jackh/thesis/janitor/simulator

if [ -z "${action}" -o -z "${url_file}" ]
then
    exit "bad input"
    exit 1
fi

set -ex

# for knowing which problem file to use
i=0


while read url
do
    ssh_opt="-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i ~/.ssh/aws.pem"
    ssh_user=ubuntu
    #ssh_opt="-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i ~/.ssh/id_rsa"
    #ssh_user=jackh
    ssh_login="${ssh_user}@${url}"
    case "${action}" in
    run)
        branch=
        simulator=
        problems_file=

        branch="janitor-centralised"
        simulator=janitor-centralised
        problems_file="problems/no-stock/part-${i}.txt"
        let i=i+1

        if [ -z "${branch}" -o -z "${problems_file}" -o -z "${simulator}" ]
        then
            echo "failed sanity check"
            exit 1
        fi
        run_cmd="./run_problems.sh -s ${simulator} -t 10 -e ${url}-unsolved-problems.txt ${problems_file} -x"
        echo ${run_cmd}
        ssh ${ssh_opt} "${ssh_user}@${url}" /bin/bash <<EOF
set -ex
cd "${repo_dir}"
git checkout "${branch}"
if [ -f results.tar.gz ]
then
    mkdir -p  ~/results-backup
    backup_file=\$(mktemp -p ~/results-backup --suffix=.tar.gz)
    mv results.tar.gz "\${backup_file}"
fi
rm -rf temp_problems logs
mkdir -p temp_problems logs/output logs/plans/roborescue
screen -d -m sh -c "${run_cmd} 2>&1 1>screen_cmd_output.txt"
EOF
        ;;
    collect)
        mkdir -p "results/unclassified"
        local_file="results/unclassified/${url}.tar.gz"
        if [ -f "${local_file}" ]
        then
            echo file "${local_file}" already exists
            exit 1
        fi
        scp ${ssh_opt} "${ssh_login}:${repo_dir}/results.tar.gz" "${local_file}"
        ;;
    *)
        echo "unrecognised action: ${action}"
        exit 1
        ;;
    esac
done < "${url_file}"